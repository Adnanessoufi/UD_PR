"""Generate a single master story using saved analysis only."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.models.content import MasterContent, SourceAnalysis
from app.services.openai_service import AIServiceError, structured_response
from app.services.campaign_service import brief_instruction, mark_preferences
from app.services.output_language import OutputLanguage, language_instruction

PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "master_content.txt"


def load_analysis(run_dir: Path) -> SourceAnalysis | None:
    path = run_dir / "analysis.json"
    if not path.is_file():
        return None
    try:
        return SourceAnalysis.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise AIServiceError(
            "Saved analysis is malformed. Please analyze the document again.", 422
        ) from exc


def save_content(run_dir: Path, content: MasterContent) -> None:
    (run_dir / "master_content.json").write_text(
        content.model_dump_json(indent=2), encoding="utf-8"
    )
    mark_preferences(run_dir, "master")


def validate_content(analysis: SourceAnalysis, content: MasterContent) -> None:
    valid_ids = {fact.id for fact in analysis.key_facts}
    if not content.source_fact_ids or any(
        fact_id not in valid_ids for fact_id in content.source_fact_ids
    ):
        raise AIServiceError("Generated content has invalid source references. Please retry.")
    if not all(
        [
            content.headline.strip(),
            content.lead.strip(),
            content.body.strip(),
            content.short_summary.strip(),
            content.press_release.strip(),
        ]
    ):
        raise AIServiceError("The AI returned incomplete content. Please retry.")


async def generate_content(
    run_dir: Path, analysis: SourceAnalysis, language: OutputLanguage = "en"
) -> MasterContent:
    if not analysis.key_facts:
        raise AIServiceError(
            "The source analysis is empty. Please analyze the document again.", 422
        )
    response = await structured_response(
        PROMPT_FILE.read_text(encoding="utf-8")
        + "\n"
        + language_instruction(language)
        + brief_instruction(run_dir),
        json.dumps(analysis.model_dump(), ensure_ascii=False),
        MasterContent,
    )
    validate_content(analysis, response)
    save_content(run_dir, response)
    return response
