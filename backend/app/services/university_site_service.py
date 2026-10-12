"""Local-only publication of saved University Website articles."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata
from uuid import UUID

from pydantic import ValidationError

from app.models.assets import AssetPack
from app.models.content import SourceAnalysis
from app.models.platform import PlatformResult
from app.services.meta_publish_service import MetaPublishError, _media
from app.services.output_language import load_output_language
from app.services.video_service import load_uploads


STORAGE = Path(__file__).resolve().parents[2] / "storage"
PUBLISHED = STORAGE / "published" / "university_site"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class UniversitySiteError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def _run_folder(run_id: UUID) -> Path:
    folder = STORAGE / str(run_id)
    if not folder.is_dir():
        raise UniversitySiteError("Document run was not found.", 404)
    return folder


def _saved_content(folder: Path) -> tuple[str, str, str, str, str]:
    try:
        platforms = PlatformResult.model_validate_json(
            (folder / "platforms.json").read_text(encoding="utf-8")
        )
        analysis = SourceAnalysis.model_validate_json(
            (folder / "analysis.json").read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise UniversitySiteError("Saved University Website content is unavailable.", 422) from exc
    if "website" not in platforms.platforms:
        raise UniversitySiteError("University Website was not selected for this run.", 409)
    if platforms.language != load_output_language(folder):
        raise UniversitySiteError(
            "Saved University Website language does not match this run. Generate the selected language first.",
            409,
        )
    post = next((item for item in platforms.items if item.platform == "website"), None)
    if post is None or not post.title.strip() or not post.body.strip():
        raise UniversitySiteError("Saved University Website article is incomplete.", 422)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", post.body) if part.strip()]
    lead = paragraphs[0]
    body = "\n\n".join(paragraphs[1:])
    category = (
        "Campus news"
        if analysis.document_type == "quick_announcement"
        else "Education"
        if re.search(
            r"curriculum|programme|program|educational|degree", analysis.document_type, re.I
        )
        else "Research"
    )
    return post.title.strip(), lead, body, analysis.title, category


def _media_record(folder: Path, media_id: str) -> dict:
    try:
        resolved = _media(folder, media_id)
    except MetaPublishError as exc:
        raise UniversitySiteError(
            f"Selected media is unavailable: {str(exc)}", exc.status_code
        ) from exc
    if resolved is None:
        raise UniversitySiteError("Selected media is unavailable.", 404)
    kind, _, route = resolved
    if kind == "video" and media_id == "generated_video":
        label, asset_type = "Generated video", "generated_video"
    elif kind == "video":
        try:
            clip = next(
                (
                    item
                    for item in load_uploads(folder)
                    if item.get("id") == media_id.removeprefix("uploaded_video:")
                ),
                None,
            )
        except (OSError, ValueError, TypeError) as exc:
            raise UniversitySiteError("Saved video uploads are unavailable.", 422) from exc
        label, asset_type = (
            (clip.get("label") or "Uploaded video") if clip else "Uploaded video",
            "uploaded_video",
        )
    else:
        try:
            pack = AssetPack.model_validate_json(
                (folder / "assets.json").read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise UniversitySiteError("Saved image assets are unavailable.", 422) from exc
        asset = next((item for item in pack.assets if item.id == media_id), None)
        if asset is None:
            raise UniversitySiteError("Selected image is unavailable.", 404)
        label, asset_type = asset.label, asset.type
    return {
        "id": media_id,
        "media_type": kind,
        "asset_type": asset_type,
        "label": label,
        "url": route,
    }


def _existing_for_run(run_id: UUID) -> dict | None:
    if not PUBLISHED.is_dir():
        return None
    language = load_output_language(STORAGE / str(run_id))
    for path in PUBLISHED.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            isinstance(record, dict)
            and record.get("run_id") == str(run_id)
            and record.get("slug") == path.stem
            and record.get("language", "en") == language
        ):
            return record
    return None


def _new_slug(headline: str, run_id: UUID, language: str) -> str:
    ascii_title = (
        unicodedata.normalize("NFKD", headline).encode("ascii", "ignore").decode("ascii").lower()
    )
    stem = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")[:70].rstrip("-") or "article"
    return f"{stem}-{language}-{run_id.hex}" if language != "en" else f"{stem}-{run_id.hex}"


def publish_article(run_id: UUID, primary_media_id: str | None, media_ids: list[str]) -> dict:
    folder = _run_folder(run_id)
    language = load_output_language(folder)
    headline, lead, body, source_title, category = _saved_content(folder)
    if len(media_ids) > 30 or len(set(media_ids)) != len(media_ids):
        raise UniversitySiteError("The selected media list is invalid.", 422)
    if primary_media_id and primary_media_id not in media_ids:
        raise UniversitySiteError("The primary media must be in the selected media list.", 422)
    if not primary_media_id and media_ids:
        raise UniversitySiteError("Choose a primary media item before publishing.", 422)
    ordered = (
        [primary_media_id, *(item for item in media_ids if item != primary_media_id)]
        if primary_media_id
        else []
    )
    media = [_media_record(folder, item) for item in ordered]
    existing = _existing_for_run(run_id)
    slug = existing["slug"] if existing else _new_slug(headline, run_id, language)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "run_id": str(run_id),
        "language": language,
        "slug": slug,
        "headline": headline,
        "lead": lead,
        "body": body,
        "published_at": existing.get("published_at", now) if existing else now,
        "updated_at": now,
        "primary_media": media[0] if media else None,
        "remaining_media": media[1:],
        "source_title": source_title,
        "category": category,
        "article_url": f"/university-news/{slug}",
    }
    PUBLISHED.mkdir(parents=True, exist_ok=True)
    path = PUBLISHED / f"{slug}.json"
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise UniversitySiteError("The demo article could not be saved.", 503) from exc
    return record


def article_for_run(run_id: UUID) -> dict | None:
    return _existing_for_run(run_id)


def load_article(slug: str) -> dict:
    if not SLUG.fullmatch(slug) or len(slug) > 120:
        raise UniversitySiteError("Article was not found.", 404)
    try:
        record = json.loads((PUBLISHED / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UniversitySiteError("Article was not found.", 404) from exc
    if not isinstance(record, dict) or record.get("slug") != slug:
        raise UniversitySiteError("Article was not found.", 404)
    return record


def list_articles() -> list[dict]:
    if not PUBLISHED.is_dir():
        return []
    records = []
    for path in PUBLISHED.glob("*.json"):
        try:
            record = load_article(path.stem)
        except UniversitySiteError:
            continue
        records.append(record)
    return sorted(records, key=lambda item: item.get("published_at", ""), reverse=True)
