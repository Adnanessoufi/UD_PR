"""Explicit Facebook Page and Instagram publishing actions."""

import asyncio
from datetime import datetime, timezone
import json
from uuid import UUID

from app.services.openai_service import AIServiceError
from app.services.verification_service import require_approval
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.meta_publish_service import (
    MetaPublishError,
    connection_status,
    instagram_jpeg_path,
    instagram_video_file,
    publication_status,
    publish_facebook,
    publish_instagram,
)


router = APIRouter(prefix="/api/meta", tags=["meta"])
LOCKS: dict[tuple[str, UUID], asyncio.Lock] = {}


class PublishRequest(BaseModel):
    primary_media_id: str | None = None


def _error(exc: MetaPublishError) -> HTTPException:
    return HTTPException(exc.status_code, {"message": str(exc), **exc.details})


@router.get("/status")
def status() -> dict:
    return connection_status()


@router.get("/{platform}/publish/{run_id}/status")
async def published_status(platform: str, run_id: UUID) -> dict:
    if platform not in {"facebook", "instagram"}:
        raise HTTPException(404, "Platform was not found.")
    try:
        return await publication_status(run_id, platform)
    except MetaPublishError as exc:
        raise _error(exc) from exc


@router.post("/{platform}/publish/{run_id}")
async def publish(platform: str, run_id: UUID, request: PublishRequest) -> dict:
    if platform not in {"facebook", "instagram"}:
        raise HTTPException(404, "Platform was not found.")
    lock = LOCKS.setdefault((platform, run_id), asyncio.Lock())
    async with lock:
        try:
            require_approval(
                Path(__file__).resolve().parents[2] / "storage" / str(run_id),
                platform,
                primary_media_id=request.primary_media_id,
            )
            if platform == "facebook":
                return await publish_facebook(run_id, request.primary_media_id)
            return await publish_instagram(run_id, request.primary_media_id)
        except AIServiceError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        except MetaPublishError as exc:
            raise _error(exc) from exc


@router.get("/media/{run_id}/{asset_id}.jpg")
@router.head("/media/{run_id}/{asset_id}.jpg", include_in_schema=False)
def instagram_jpeg(run_id: UUID, asset_id: str, request: Request) -> FileResponse:
    try:
        path = instagram_jpeg_path(run_id, asset_id)
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "preflight": request.headers.get("x-ud-instagram-preflight") == "1",
        }
        try:
            with (path.parents[2] / "instagram_media_requests.jsonl").open(
                "a", encoding="utf-8"
            ) as trace:
                trace.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # Media serving must not depend on diagnostic storage.
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    except MetaPublishError as exc:
        raise _error(exc) from exc


@router.get("/media/{run_id}/instagram.mp4")
@router.head("/media/{run_id}/instagram.mp4", include_in_schema=False)
def instagram_mp4(run_id: UUID, request: Request) -> FileResponse:
    try:
        path = instagram_video_file(run_id)
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "media": "video",
            "preflight": request.headers.get("x-ud-instagram-preflight") == "1",
        }
        try:
            with (path.parents[1] / "instagram_media_requests.jsonl").open(
                "a", encoding="utf-8"
            ) as trace:
                trace.write(json.dumps(entry) + "\n")
        except OSError:
            pass
        return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "no-store"})
    except MetaPublishError as exc:
        raise _error(exc) from exc
