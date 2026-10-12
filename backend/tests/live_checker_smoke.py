"""Small opt-in live API check with synthetic text; never approves or publishes."""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from app.models.verification import CheckerResult, Evidence
from app.services.openai_service import AIServiceError, structured_response
from app.services.verification_service import confirmed_excerpt, number_checks

SOURCE = "In a computer simulation of 339 samples, the system achieved 88.8% accuracy. The system has not been validated in field deployments."
UNITS = [
    {
        "id": "supported",
        "text": "In a simulation of 339 samples, the system achieved 88.8% accuracy.",
    },
    {"id": "exaggerated", "text": "The system achieved 88.8% accuracy in field deployment."},
    {"id": "invented_number", "text": "In simulation, the system achieved 99.9% accuracy."},
]


async def main():
    prompt = Path("app/prompts/check_claims.txt").read_text(encoding="utf-8")
    passages = [{"id": "P1", "page": 1, "source_type": "document", "text": SOURCE, "url": None}]
    result = await structured_response(
        prompt,
        json.dumps(
            {"units": UNITS, "source_passages": passages, "limitations": ["Simulation only."]}
        ),
        CheckerResult,
        checker=True,
    )
    if len(result.items) != len(UNITS) or {x.id for x in result.items} != {x["id"] for x in UNITS}:
        raise RuntimeError("Live checker omitted or duplicated units.")
    results = []
    by_id = {x.id: x for x in result.items}
    for unit in UNITS:
        item = by_id[unit["id"]]
        evidence = []
        invalid = False
        for ref in item.evidence:
            quote = confirmed_excerpt(ref.excerpt, SOURCE) if ref.passage_id == "P1" else None
            if not quote:
                invalid = True
            else:
                evidence.append(
                    Evidence(passage_id="P1", page=1, source_type="document", excerpt=quote)
                )
        checks = number_checks(unit["text"], evidence, passages)
        passed = (
            item.verdict == "supported"
            and bool(evidence)
            and not invalid
            and all(c.status == "matched" for c in checks)
            if unit["id"] == "supported"
            else item.verdict in {"unsupported", "exaggerated", "needs_review"}
        )
        if unit["id"] == "invented_number":
            passed = passed and any(c.status == "missing_source" for c in checks)
        results.append(
            {
                "id": unit["id"],
                "text": unit["text"],
                "verdict": item.verdict,
                "explanation": item.explanation,
                "evidence": [e.model_dump() for e in evidence],
                "number_checks": [c.model_dump() for c in checks],
                "passed": passed,
            }
        )
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "writer_model": os.getenv("OPENAI_MODEL"),
        "checker_model": os.getenv("OPENAI_CHECKER_MODEL"),
        "source": SOURCE,
        "passed": all(x["passed"] for x in results),
        "results": results,
        "limitation": "Three synthetic smoke-test cases; not an empirical accuracy benchmark.",
    }
    output = Path("../docs/LIVE_CHECKER_SMOKE.json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "results": [
                    {"id": r["id"], "verdict": r["verdict"], "passed": r["passed"]} for r in results
                ],
            }
        )
    )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AIServiceError as exc:
        print(str(exc))
        raise SystemExit(1)
