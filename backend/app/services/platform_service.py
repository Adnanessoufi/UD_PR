"""Adapt one saved master story to selected platforms in one request."""

import json
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from app.models.content import MasterContent
from app.models.platform import PlatformAdaptations, PlatformRequest, PlatformResult
from app.services.content_service import (
    generate_content,
    load_analysis,
    save_content,
    validate_content,
)
from app.services.openai_service import AIServiceError, structured_response
from app.services.campaign_service import brief_instruction, preferences_match, mark_preferences
from app.services.output_language import (
    language_instruction,
    load_output_language,
    save_output_language,
)

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
RULES = {
    "website": {"text"},
    "linkedin": {"text", "image", "video"},
    "facebook": {"text", "image", "video"},
    "instagram": {"image", "video"},
    "tiktok": {"video"},
    "youtube": {"video"},
}


def validate_selection(selection: PlatformRequest, *, quick_announcement: bool = False) -> None:
    types = set(selection.content_types)
    platforms = selection.platforms
    if not types or not platforms:
        raise AIServiceError("Select at least one content type and one platform.", 422)
    if len(types) != len(selection.content_types) or len(set(platforms)) != len(platforms):
        raise AIServiceError("Each content type and platform can be selected only once.", 422)
    for platform in platforms:
        if not types.intersection(RULES[platform]) and not (
            quick_announcement and platform == "tiktok" and "text" in types
        ):
            raise AIServiceError(
                f"{platform.title()} is unavailable for the selected content types.", 422
            )


def load_master(run_dir: Path) -> MasterContent:
    path = run_dir / "master_content.json"
    if not path.is_file():
        raise AIServiceError("Source analysis is still finishing. Please try again shortly.", 409)
    try:
        return MasterContent.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise AIServiceError("Saved master content could not be read.", 422) from exc


def validate_posts(result: PlatformResult, approved_ids: set[str]) -> None:
    if [item.platform for item in result.items] != result.platforms:
        raise AIServiceError("Platform output did not match the selected platforms. Please retry.")
    for item in result.items:
        if not item.body.strip() or not item.source_fact_ids:
            raise AIServiceError("A platform text was incomplete. Please retry.")
        if any(fact_id not in approved_ids for fact_id in item.source_fact_ids):
            raise AIServiceError(
                "A platform text cited facts outside the master story. Please retry."
            )


def save_platforms(run_dir: Path, result: PlatformResult) -> None:
    (run_dir / "platforms.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    mark_preferences(run_dir, "platform")


def load_platforms(run_dir: Path) -> PlatformResult | None:
    path = run_dir / "platforms.json"
    if not path.is_file():
        return None
    try:
        return PlatformResult.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise AIServiceError("Saved platform previews could not be read.", 422) from exc


async def create_platforms(
    run_dir: Path, selection: PlatformRequest, *, regenerate: bool = False
) -> PlatformResult:
    quick_announcement = (run_dir / "quick_announcement.json").is_file()
    validate_selection(selection, quick_announcement=quick_announcement)
    analysis = load_analysis(run_dir)
    if analysis is None:
        raise AIServiceError("Source analysis is missing. Please process the document first.", 404)
    language_changed = load_output_language(run_dir) != selection.language
    preferences_changed = not preferences_match(run_dir, "master") or not preferences_match(
        run_dir, "platform"
    )
    if language_changed or not preferences_match(run_dir, "master"):
        if quick_announcement:
            from app.services.quick_announcement_service import CONTENT_PROMPT

            quick = json.loads((run_dir / "quick_announcement.json").read_text(encoding="utf-8"))
            payload = {
                "announcement": quick["original_announcement"],
                "approved_facts": [fact.model_dump() for fact in analysis.key_facts],
                "serious_contradiction": quick.get("warning"),
                "output_language": selection.language,
            }
            master = await structured_response(
                CONTENT_PROMPT
                + "\n"
                + language_instruction(selection.language)
                + brief_instruction(run_dir),
                json.dumps(payload, ensure_ascii=False),
                MasterContent,
            )
            validate_content(analysis, master)
            save_content(run_dir, master)
        else:
            master = await generate_content(run_dir, analysis, selection.language)
        save_output_language(run_dir, selection.language)
    else:
        master = load_master(run_dir)
    approved_ids = set(master.source_fact_ids)
    if not approved_ids:
        raise AIServiceError("The master story has no grounded facts.", 422)

    existing = load_platforms(run_dir)
    saved = (
        {item.platform: item for item in existing.items}
        if existing
        and not language_changed
        and not preferences_changed
        and existing.language == selection.language
        else {}
    )

    missing = [
        name
        for name in selection.platforms
        if regenerate
        or name not in saved
        or not saved[name].body.strip()
        or not saved[name].source_fact_ids
        or any(fact_id not in approved_ids for fact_id in saved[name].source_fact_ids)
    ]
    if not missing:
        return PlatformResult(
            **selection.model_dump(), items=[saved[name] for name in selection.platforms]
        )

    facts = [fact.model_dump() for fact in analysis.key_facts if fact.id in approved_ids]
    if not facts:
        raise AIServiceError("The master story's source facts are missing.", 422)
    prompt = (
        (PROMPT_DIR / "platform_base.txt").read_text(encoding="utf-8")
        + "\n"
        + language_instruction(selection.language)
        + brief_instruction(run_dir)
    )
    if quick_announcement:
        prompt += (
            "\nQuick announcement: lead with the supplied achievement once, then use relevant web-supported "
            "event or person context from the approved facts. Do not restate the input as filler. "
            "Omit missing details instead of saying they were not provided or unverified. "
            "Do not infer a person's university role without a supporting fact.\n"
        )
    prompt += "\n\n".join(
        (
            "TIKTOK: Write a 20–60-word factual caption for a possible photo post. Do not refer to a video."
            if quick_announcement and platform == "tiktok"
            else (PROMPT_DIR / f"ud_{platform}.txt").read_text(encoding="utf-8")
        )
        for platform in missing
    )
    payload = {
        "content_types": selection.content_types,
        "platforms_in_order": missing,
        "master_content": master.model_dump(),
        "approved_source_facts": facts,
        "output_language": selection.language,
    }
    started = perf_counter()
    generated = await structured_response(
        prompt, json.dumps(payload, ensure_ascii=False), PlatformAdaptations
    )
    print(
        f"[{run_dir.name}] OpenAI platform adaptation: {perf_counter() - started:.1f}s", flush=True
    )
    by_platform = {item.platform: item for item in generated.items}
    if len(by_platform) != len(generated.items) or set(by_platform) != set(missing):
        raise AIServiceError("Platform output did not match the selected platforms. Please retry.")
    saved.update(by_platform)
    result = PlatformResult(
        **selection.model_dump(),
        items=[saved[platform] for platform in selection.platforms],
    )
    validate_posts(result, approved_ids)
    same_language = (
        existing is not None
        and not language_changed
        and not preferences_changed
        and existing.language == selection.language
    )
    all_names = list(
        dict.fromkeys((existing.platforms if same_language else []) + selection.platforms)
    )
    all_types = list(
        dict.fromkeys((existing.content_types if same_language else []) + selection.content_types)
    )
    save_platforms(
        run_dir,
        PlatformResult(
            content_types=all_types,
            platforms=all_names,
            language=selection.language,
            items=[saved[name] for name in all_names],
        ),
    )
    return result
