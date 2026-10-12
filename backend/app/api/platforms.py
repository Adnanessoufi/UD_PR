"""Generate and save final platform text previews."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.models.platform import PlatformRequest, PlatformResult
from app.services.openai_service import AIServiceError
from app.services.output_language import load_output_language
from app.services.platform_service import (
    create_platforms,
    load_master,
    save_platforms,
    validate_posts,
    validate_selection,
)

router = APIRouter(prefix="/api")
STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"


def run_folder(run_id: UUID) -> Path:
    folder = STORAGE_DIR / str(run_id)
    if not folder.is_dir():
        raise HTTPException(
            status_code=404, detail="Document run was not found. Please upload again."
        )
    return folder


@router.post("/platforms/{run_id}", response_model=PlatformResult)
async def generate_platforms(run_id: UUID, selection: PlatformRequest) -> PlatformResult:
    try:
        return await create_platforms(run_folder(run_id), selection)
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/platforms/{run_id}/regenerate", response_model=PlatformResult)
async def regenerate_platforms(run_id: UUID, selection: PlatformRequest) -> PlatformResult:
    try:
        return await create_platforms(run_folder(run_id), selection, regenerate=True)
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put("/platforms/{run_id}", response_model=PlatformResult)
async def update_platforms(run_id: UUID, result: PlatformResult) -> PlatformResult:
    folder = run_folder(run_id)
    existing_path = folder / "platforms.json"
    if not existing_path.is_file():
        raise HTTPException(
            status_code=404, detail="Platform previews have not been generated yet."
        )
    try:
        existing = PlatformResult.model_validate_json(existing_path.read_text(encoding="utf-8"))
        if result.language != existing.language or result.language != load_output_language(folder):
            raise AIServiceError("Saved platform language does not match this run.", 422)
        validate_selection(
            result, quick_announcement=(folder / "quick_announcement.json").is_file()
        )
        if not set(result.content_types).issubset(existing.content_types) or not set(
            result.platforms
        ).issubset(existing.platforms):
            raise AIServiceError(
                "Selected formats and platforms cannot be changed while saving edits.", 422
            )
        master = load_master(folder)
        validate_posts(result, set(master.source_fact_ids))
        edits = {item.platform: item for item in result.items}
        existing.items = [edits.get(item.platform, item) for item in existing.items]
        save_platforms(folder, existing)
        return result
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail="Saved platform previews could not be read."
        ) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
