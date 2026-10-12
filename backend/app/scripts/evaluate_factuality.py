"""Dataset-driven live checker evaluation; dry-run validates cases without API calls."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from pydantic import BaseModel, Field
from app.models.verification import CheckerResult, Evidence
from app.services.model_gateway import describe
from app.services.openai_service import AIServiceError, structured_response
from app.services.verification_service import confirmed_excerpt, number_checks


class Case(BaseModel):
    id: str = Field(min_length=1)
    source: str = Field(min_length=10)
    claim: str = Field(min_length=6)
    should_flag: bool


def load_cases(path: Path) -> list[Case]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [Case.model_validate(item) for item in data]
    if not cases or len({case.id for case in cases}) != len(cases):
        raise ValueError("Evaluation requires nonempty cases with unique IDs.")
    return cases


def score(expected_flags: list[bool], predicted_flags: list[bool]) -> dict:
    if len(expected_flags) != len(predicted_flags) or not expected_flags:
        raise ValueError("Expected and predicted labels must be nonempty and aligned.")
    tp = sum(e and p for e, p in zip(expected_flags, predicted_flags))
    fp = sum(not e and p for e, p in zip(expected_flags, predicted_flags))
    fn = sum(e and not p for e, p in zip(expected_flags, predicted_flags))
    tn = sum(not e and not p for e, p in zip(expected_flags, predicted_flags))
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "flag_precision": tp / (tp + fp) if tp + fp else None,
        "flag_recall": tp / (tp + fn) if tp + fn else None,
        "accuracy": (tp + tn) / len(expected_flags),
    }


async def evaluate(cases: list[Case]) -> dict:
    prompt = (Path(__file__).resolve().parents[1] / "prompts/check_claims.txt").read_text(
        encoding="utf-8"
    )
    results = []
    for case in cases:
        passages = [
            {"id": "P1", "page": 1, "source_type": "document", "text": case.source, "url": None}
        ]
        started = perf_counter()
        response = await structured_response(
            prompt,
            json.dumps(
                {
                    "units": [{"id": case.id, "text": case.claim}],
                    "source_passages": passages,
                    "limitations": [],
                },
                ensure_ascii=False,
            ),
            CheckerResult,
            checker=True,
        )
        if len(response.items) != 1 or response.items[0].id != case.id:
            raise AIServiceError("Checker omitted or duplicated an evaluation case.", 502)
        item = response.items[0]
        evidence = []
        invalid = False
        for reference in item.evidence:
            quote = (
                confirmed_excerpt(reference.excerpt, case.source)
                if reference.passage_id == "P1"
                else None
            )
            if quote:
                evidence.append(
                    Evidence(passage_id="P1", source_type="document", page=1, excerpt=quote)
                )
            else:
                invalid = True
        checks = number_checks(case.claim, evidence, passages)
        predicted = (
            item.verdict in {"unsupported", "exaggerated", "needs_review"}
            or invalid
            or (item.verdict == "supported" and not evidence)
            or any(c.status != "matched" for c in checks)
        )
        results.append(
            {
                "id": case.id,
                "expected_flag": case.should_flag,
                "predicted_flag": predicted,
                "verdict": item.verdict,
                "explanation": item.explanation,
                "seconds": round(perf_counter() - started, 3),
                "number_checks": [c.model_dump() for c in checks],
            }
        )
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "provider": describe(),
        "case_count": len(cases),
        "metrics": score(
            [x["expected_flag"] for x in results], [x["predicted_flag"] for x in results]
        ),
        "results": results,
        "limitation": "Results apply only to this labelled dataset. Small synthetic sets are not general accuracy benchmarks.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path("evals/factuality.json"))
    parser.add_argument("--output", type=Path, default=Path("../docs/FACTUALITY_EVALUATION.json"))
    parser.add_argument("--live", action="store_true", help="Opt in to paid model requests.")
    args = parser.parse_args()
    cases = load_cases(args.cases)
    if not args.live:
        print(
            json.dumps(
                {"validated_cases": len(cases), "case_ids": [c.id for c in cases], "api_calls": 0}
            )
        )
        return
    report = asyncio.run(evaluate(cases))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"case_count": report["case_count"], "metrics": report["metrics"]}))


if __name__ == "__main__":
    try:
        main()
    except AIServiceError as exc:
        print(str(exc))
        raise SystemExit(1)
    except ValueError:
        print("Evaluation dataset is invalid. Check the case schema and unique IDs.")
        raise SystemExit(2)
