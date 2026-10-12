"""Read-only demo readiness report and local draft exports; no AI generation or publishing."""

import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    ids = json.loads((root / "docs/REHEARSAL_CAMPAIGNS.json").read_text(encoding="utf-8"))
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
        "model_generation_requests": 0,
        "external_posts_sent": 0,
        "human_approvals_created": 0,
    }

    def record(name, passed, **details):
        report["checks"].append({"name": name, "passed": passed, **details})

    with httpx.Client(base_url=args.server.rstrip("/"), timeout=60) as client:
        capabilities = client.get("/api/system/capabilities")
        capabilities.raise_for_status()
        data = capabilities.json()
        record(
            "API and task discovery",
            {
                "document.process",
                "source.analyze",
                "master.generate",
                "platforms.generate",
                "verification.check",
                "story.answer",
            }.issubset({task["id"] for task in data["tasks"]}),
            tasks=len(data["tasks"]),
            writer_ready=data["provider"]["writer_ready"],
            checker_ready=data["provider"]["checker_ready"],
        )
        for key in ("original_flagged_paper", "corrected_paper", "fresh_docx", "news", "video"):
            run = ids[key]
            response = client.get(f"/api/campaigns/{run}")
            response.raise_for_status()
            bundle = response.json()
            record(
                f"Reopen {key}",
                bool(bundle["combined"]),
                language=bundle["workspace"]["language"],
                run_id=run,
            )
            if key in ("original_flagged_paper", "corrected_paper", "fresh_docx"):
                context = {
                    "platforms": bundle["workspace"]["platforms"],
                    "primary_media_id": None,
                    "media_ids": [],
                }
                current = client.post(f"/api/verification/{run}/status", json=context)
                current.raise_for_status()
                status = current.json()
                expected = (
                    status["blocking_count"] > 0
                    if key == "original_flagged_paper"
                    else status["state"] == "verified"
                )
                record(
                    f"Validation {key}",
                    expected,
                    state=status["state"],
                    blocking=status["blocking_count"],
                    units=len((status["report"] or {}).get("claims", [])),
                    approved=status["approval"] is not None,
                )
            response = client.get(
                f"/api/campaigns/{run}/export", params={"include_media": key == "video"}
            )
            response.raise_for_status()
            with ZipFile(BytesIO(response.content)) as archive:
                valid = archive.testzip() is None and "manifest.json" in archive.namelist()
                entries = archive.namelist()
                if key == "video":
                    valid = valid and any(name.endswith(".mp4") for name in entries)
                record(
                    f"ZIP export {key}", valid, entries=len(entries), bytes=len(response.content)
                )
            (root / "docs" / f"REHEARSAL_{key.upper()}_PACKAGE.zip").write_bytes(response.content)
        evidence = client.get(f"/api/verification/{ids['original_flagged_paper']}/evidence/C1/0")
        record(
            "Original PDF highlights",
            evidence.status_code == 200
            and evidence.headers.get("x-evidence-highlighted") == "true",
        )
        status = client.get(f"/api/video/{ids['video']}/status")
        status.raise_for_status()
        record(
            "Cached video ready",
            status.json()["stage"] == "ready",
            language=status.json().get("language"),
        )
        for name in ("meta", "youtube", "tiktok"):
            response = client.get(f"/api/{name}/status")
            # Do not write OAuth records, account details or tokens to the report.
            record(
                f"{name} connection status endpoint",
                response.status_code == 200,
                note="Status endpoint reachable; no real publication attempted.",
            )
        jobs = client.get(f"/api/jobs/runs/{ids['corrected_paper']}")
        jobs.raise_for_status()
        completed = [
            j for j in jobs.json() if j["task_id"] == "document.process" and j["state"] == "ready"
        ]
        record("Completed background task recovery", bool(completed), count=len(completed))
    report["all_passed"] = all(check["passed"] for check in report["checks"])
    output = root / "docs/REHEARSAL_REPORT.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    raise SystemExit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()
