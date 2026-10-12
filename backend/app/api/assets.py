"""Create visual asset packs from saved runs and serve their image files."""

from pathlib import Path
import re
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.models.assets import AssetPack, AssetRequest, MainAssetRequest
from app.services.asset_service import (
    create_assets,
    delete_asset,
    regenerate_image,
    select_main,
    upload_image,
)
from app.services.openai_service import AIServiceError

router = APIRouter(prefix="/api/assets")
STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"


def run_folder(run_id: UUID) -> Path:
    folder = STORAGE_DIR / str(run_id)
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="Document run was not found.")
    return folder


@router.post("/{run_id}", response_model=AssetPack)
async def generate_assets(run_id: UUID, request: AssetRequest) -> AssetPack:
    try:
        return await create_assets(run_folder(run_id), request.platforms)
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{run_id}/regenerate", response_model=AssetPack)
async def regenerate_generated_visual(run_id: UUID) -> AssetPack:
    try:
        return await regenerate_image(run_folder(run_id))
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put("/{run_id}/main", response_model=AssetPack)
async def set_main_asset(run_id: UUID, request: MainAssetRequest) -> AssetPack:
    try:
        return select_main(run_folder(run_id), request.asset_id)
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{run_id}/upload", response_model=AssetPack)
async def add_uploaded_image(run_id: UUID, file: UploadFile = File(...)) -> AssetPack:
    try:
        return await upload_image(run_folder(run_id), file)
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/{run_id}/{asset_id}", response_model=AssetPack)
async def remove_asset(run_id: UUID, asset_id: str) -> AssetPack:
    try:
        return delete_asset(run_folder(run_id), asset_id)
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/{run_id}/files/uploads/{filename}")
async def uploaded_asset_file(run_id: UUID, filename: str) -> FileResponse:
    if not re.fullmatch(r"[0-9a-f]{32}\.(png|jpg|webp)", filename):
        raise HTTPException(status_code=404, detail="Asset was not found.")
    path = run_folder(run_id) / "assets" / "uploads" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset was not found.")
    media_type = (
        "image/jpeg"
        if filename.endswith(".jpg")
        else "image/webp"
        if filename.endswith(".webp")
        else "image/png"
    )
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-store"})


@router.get("/{run_id}/files/{filename}")
async def asset_file(run_id: UUID, filename: str) -> FileResponse:
    if filename not in {
        "publication_preview.png",
        "source_visual.png",
        "programme_card.png",
        "generated_explainer.png",
        "generated_education_visual.png",
    }:
        raise HTTPException(status_code=404, detail="Asset was not found.")
    path = run_folder(run_id) / "assets" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset was not found.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
