"""Resume only the four incomplete demo runs, one document at a time."""

import asyncio
import json
import os
from pathlib import Path

from openai import APIConnectionError, APITimeoutError

from app.models.platform import PlatformRequest
from app.services import analysis_service, asset_service, content_service, platform_service
from app.services.analysis_service import analyze_source
from app.services.asset_service import create_assets, family_for
from app.services.cache_service import (
    DEMO_PLATFORMS,
    STORAGE_DIR,
    availability,
    register,
    sha256_file,
)
from app.services.content_service import generate_content, load_analysis, validate_content
from app.services.openai_service import AIServiceError
from app.services.platform_service import create_platforms, load_master, load_platforms

SUMMARY_PATH = STORAGE_DIR / "demo_preparation_summary.json"
TARGETS = (
    ("1-s2.0-S0038092X26000496-main.pdf", "e6d1f84e-69e0-41fe-8271-6243db01172b"),
    ("1-s2.0-S2590123026011850-main.pdf", "222b240b-2b6a-4e74-9552-efa3008d0486"),
    (
        "Osztatlan IT_matematika_fizika tanár_2025 tanterv_2025.pdf",
        "9a53722c-7ecc-4942-a745-96f70ae3e88e",
    ),
    ("Tardi_2026_PASP_138_044506.pdf", "473d1981-0d07-4e65-a7e7-9d09100a2e37"),
)
counter = {"requests": 0, "retries": 0}


def count_text_requests() -> None:
    for module in (analysis_service, content_service, platform_service):
        original = module.structured_response

        async def counted(*args, _original=original, **kwargs):
            counter["requests"] += 1
            return await _original(*args, **kwargs)

        module.structured_response = counted


def count_image_requests() -> None:
    original = asset_service._generate_image

    async def counted(*args, **kwargs):
        if os.getenv("OPENAI_IMAGE_MODEL", "").strip() and os.getenv("OPENAI_API_KEY", "").strip():
            counter["requests"] += 1
        return await original(*args, **kwargs)

    asset_service._generate_image = counted


def network_failure(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, (APIConnectionError, APITimeoutError)):
            return True
        current = current.__cause__
    return False


async def text_stage(label: str, operation):
    try:
        return await operation()
    except AIServiceError as exc:
        if not network_failure(exc):
            raise
        counter["retries"] += 1
        print(f"    {label}: transient connection error; retrying once", flush=True)
        await asyncio.sleep(3)
        return await operation()


async def image_stage(run_dir: Path):
    pack = await create_assets(run_dir, list(DEMO_PLATFORMS))
    if availability(run_dir)["assets"]:
        return pack
    error = pack.image_error or "Visual asset pack remains incomplete."
    if "connection error" not in error.lower() and "timed out" not in error.lower():
        raise RuntimeError(error)
    counter["retries"] += 1
    print("    image: transient connection error; retrying once", flush=True)
    await asyncio.sleep(3)
    pack = await create_assets(run_dir, list(DEMO_PLATFORMS))
    if not availability(run_dir)["assets"]:
        raise RuntimeError(pack.image_error or "Visual asset pack remains incomplete after retry.")
    return pack


def save_progress(summary: dict) -> None:
    documents = summary["documents"]
    summary["files_discovered"] = len(documents)
    summary["successfully_prepared"] = sum(item["ready_for_demo"] for item in documents)
    summary["failed"] = sum(not item["ready_for_demo"] for item in documents)
    summary["recovery_openai_requests"] = counter["requests"]
    summary["recovery_retries"] = counter["retries"]
    temporary = SUMMARY_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(SUMMARY_PATH)


async def recover() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    records = {item["run_id"]: item for item in summary["documents"]}
    # Verify all four exact source bytes before making the first API request.
    for filename, run_id in TARGETS:
        record = records[run_id]
        source = STORAGE_DIR / run_id / "source.pdf"
        if not source.is_file() or sha256_file(source) != record["sha256"]:
            raise RuntimeError(f"Source bytes do not match the cache entry for {run_id}.")
        if not (STORAGE_DIR / run_id / "extracted_text.json").is_file():
            raise RuntimeError(f"Saved extraction is missing for {run_id}.")
        record["filename"] = filename
    count_text_requests()
    count_image_requests()
    save_progress(summary)

    for number, (filename, run_id) in enumerate(TARGETS, 1):
        run_dir = STORAGE_DIR / run_id
        record = records[run_id]
        print(f"[{number}/4] {filename} ({run_id})", flush=True)
        record["error"] = None
        try:
            analysis = load_analysis(run_dir)
            if analysis is None:
                analysis = await text_stage("analysis", lambda: analyze_source(run_dir))
                record["analysis"] = "generated"
            else:
                record["analysis"] = "reused"
            record["document_family"] = family_for(analysis)
            save_progress(summary)
            print(f"  analysis: {record['analysis']}", flush=True)

            if (run_dir / "master_content.json").is_file():
                master = load_master(run_dir)
                validate_content(analysis, master)
                record["master_content"] = "reused"
            else:
                await text_stage("master content", lambda: generate_content(run_dir, analysis))
                record["master_content"] = "generated"
            save_progress(summary)
            print(f"  master content: {record['master_content']}", flush=True)

            prior = load_platforms(run_dir)
            present = (
                {
                    item.platform
                    for item in prior.items
                    if item.body.strip() and item.source_fact_ids
                }
                if prior
                else set()
            )
            missing = [name for name in DEMO_PLATFORMS if name not in present]
            if missing:
                await text_stage(
                    "platform text",
                    lambda: create_platforms(
                        run_dir,
                        PlatformRequest(
                            content_types=["text", "image"], platforms=list(DEMO_PLATFORMS)
                        ),
                    ),
                )
            record["platform_details"] = {
                name: "generated" if name in missing else "reused" for name in DEMO_PLATFORMS
            }
            record["platforms"] = "generated" if missing else "reused"
            save_progress(summary)
            print(
                f"  platforms: {record['platforms']} ({', '.join(missing) if missing else 'all reused'})",
                flush=True,
            )

            if availability(run_dir)["assets"]:
                pack = asset_service._load(run_dir)
                record["assets"] = "reused"
            else:
                pack = await image_stage(run_dir)
                record["assets"] = "generated"
            record["asset_count"] = len(pack.assets)
            record["ready_for_demo"] = all(availability(run_dir).values())
            if not record["ready_for_demo"]:
                raise RuntimeError("Saved results are still incomplete.")
            print(
                f"  assets: {record['assets']} ({record['asset_count']}); video: SKIPPED; READY",
                flush=True,
            )
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["ready_for_demo"] = False
            print(f"  video: SKIPPED; FAILED: {record['error']}", flush=True)
        finally:
            register(record["sha256"], run_dir, filename)
            save_progress(summary)
    print(
        f"Recovery complete: {summary['successfully_prepared']}/6 ready; "
        f"OpenAI requests: {counter['requests']}; stage retries: {counter['retries']}",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(recover())
