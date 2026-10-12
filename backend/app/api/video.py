"""Video jobs, uploaded footage, and final master video delivery."""

import asyncio
from pathlib import Path
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from moviepy import VideoFileClip

from app.services.content_service import load_analysis
from app.services.openai_service import AIServiceError
from app.services.platform_service import load_master
from app.services.output_language import load_output_language
from app.services.video_cache import cached_video_file
from app.services.video_service import (
    VideoError,
    config,
    load_status,
    load_uploads,
    run_video_job,
    save_status,
    save_uploads,
    video_dir,
)

router = APIRouter(prefix="/api/video")
STORAGE = Path(__file__).resolve().parents[2] / "storage"
JOBS: dict[str, asyncio.Task] = {}
EXTENSIONS = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
MAX_UPLOAD = 200 * 1024 * 1024


def run_folder(run_id: UUID) -> Path:
    folder = STORAGE / str(run_id)
    if not folder.is_dir():
        raise HTTPException(404, "Document run was not found.")
    return folder


def _active(run_id: UUID) -> bool:
    task = JOBS.get(str(run_id))
    return bool(task and not task.done())


def _has_final(folder: Path) -> bool:
    return cached_video_file(folder) is not None


def _ready_status(folder: Path) -> dict:
    previous = load_status(folder)
    if previous.get("language", "en") != load_output_language(folder):
        previous = {}
    url = (
        previous.get("url")
        if previous.get("stage") == "ready" and previous.get("url")
        else f"/api/video/{folder.name}/file"
    )
    return {
        **previous,
        "stage": "ready",
        "url": url,
        "error": None,
        "language": load_output_language(folder),
    }


@router.post("/{run_id}", status_code=202)
async def start_video(run_id: UUID, fail_fast: bool = False) -> dict:
    return await _start_video(run_id, fail_fast=fail_fast, regenerate=False)


@router.post("/{run_id}/regenerate", status_code=202)
async def regenerate_video(run_id: UUID, fail_fast: bool = False) -> dict:
    return await _start_video(run_id, fail_fast=fail_fast, regenerate=True)


async def _start_video(run_id: UUID, *, fail_fast: bool, regenerate: bool) -> dict:
    folder = run_folder(run_id)
    if not regenerate and _has_final(folder):
        return _ready_status(folder)
    if _active(run_id):
        status = load_status(folder)
        if status.get("language", "en") != load_output_language(folder):
            raise HTTPException(
                409, "Wait for the current video job before creating another language."
            )
        return status
    try:
        config()
        if load_analysis(folder) is None:
            raise VideoError("Saved analysis.json is required for video.", 404)
        load_master(folder)
    except VideoError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    uploads = load_uploads(folder)
    status = save_status(
        folder,
        "planning",
        error=None,
        url=None,
        clips_done=0,
        clips_total=0,
        language=load_output_language(folder),
    )
    task = asyncio.create_task(run_video_job(folder, uploads, fail_fast=fail_fast))
    JOBS[str(run_id)] = task
    task.add_done_callback(
        lambda finished: JOBS.pop(str(run_id), None) if JOBS.get(str(run_id)) is finished else None
    )
    return status


@router.get("/{run_id}/status")
async def video_status(run_id: UUID) -> dict:
    folder = run_folder(run_id)
    status = load_status(folder)
    if _active(run_id) and status.get("language", "en") == load_output_language(folder):
        return status
    if _has_final(folder):
        return _ready_status(folder)
    if status.get("language", "en") != load_output_language(folder):
        return {
            "stage": "idle",
            "url": None,
            "error": None,
            "language": load_output_language(folder),
        }
    if status["stage"] == "ready":
        return {
            **status,
            "stage": "failed",
            "url": None,
            "error": "Final video file is missing. Generate video to create it.",
        }
    if status["stage"] in {
        "planning",
        "narration",
        "generating_clips",
        "composing",
    } and not _active(run_id):
        return save_status(
            folder,
            "failed",
            error="Video job was interrupted by a server restart. Regenerate to resume.",
            url=None,
        )
    return status


@router.get("/{run_id}/uploads")
async def list_video_uploads(run_id: UUID) -> list[dict]:
    return load_uploads(run_folder(run_id))


@router.post("/{run_id}/uploads")
async def add_video_upload(run_id: UUID, file: UploadFile = File(...)) -> dict:
    folder = run_folder(run_id)
    extension = Path(file.filename or "").suffix.lower()
    if extension not in EXTENSIONS:
        raise HTTPException(415, "Upload an MP4, MOV, or WEBM video clip.")
    if _active(run_id):
        raise HTTPException(409, "Wait for the current video job before changing uploaded clips.")
    upload_dir = video_dir(folder) / "uploads"
    upload_dir.mkdir(exist_ok=True)
    clip_id = uuid4().hex
    filename = clip_id + extension
    path = upload_dir / filename
    total = 0
    try:
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD:
                    raise HTTPException(413, "Video clip exceeds the 200 MB upload limit.")
                output.write(chunk)
        with VideoFileClip(str(path), audio=False) as probe:
            duration = float(probe.duration)
            if duration < 0.5:
                raise HTTPException(
                    422, "Video clip must contain at least half a second of footage."
                )
        item = {
            "id": clip_id,
            "filename": filename,
            "label": Path(file.filename or "video clip").name,
            "duration_seconds": round(duration, 2),
            "url": f"/api/video/{run_id}/uploads/{filename}",
        }
        uploads = load_uploads(folder)
        uploads.append(item)
        save_uploads(folder, uploads)
        return item
    except Exception as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(422, f"Could not read uploaded video: {exc}") from exc
    finally:
        await file.close()


@router.delete("/{run_id}/uploads/{clip_id}")
async def delete_video_upload(run_id: UUID, clip_id: str) -> list[dict]:
    folder = run_folder(run_id)
    if _active(run_id):
        raise HTTPException(409, "Wait for the current video job before deleting uploaded clips.")
    uploads = load_uploads(folder)
    item = next((clip for clip in uploads if clip["id"] == clip_id), None)
    if item is None:
        raise HTTPException(404, "Uploaded video clip was not found.")
    (folder / "video" / "uploads" / item["filename"]).unlink(missing_ok=True)
    remaining = [clip for clip in uploads if clip["id"] != clip_id]
    save_uploads(folder, remaining)
    return remaining


@router.get("/{run_id}/uploads/{filename}")
async def uploaded_video_file(run_id: UUID, filename: str) -> FileResponse:
    if not re.fullmatch(r"[0-9a-f]{32}\.(mp4|mov|webm)", filename):
        raise HTTPException(404, "Uploaded video clip was not found.")
    folder = run_folder(run_id)
    if filename not in {item["filename"] for item in load_uploads(folder)}:
        raise HTTPException(404, "Uploaded video clip was not found.")
    path = folder / "video" / "uploads" / filename
    if not path.is_file():
        raise HTTPException(404, "Uploaded video clip was not found.")
    return FileResponse(
        path, media_type=EXTENSIONS[Path(filename).suffix], headers={"Cache-Control": "no-store"}
    )


@router.get("/{run_id}/file")
async def final_video_file(run_id: UUID) -> FileResponse:
    path = cached_video_file(run_folder(run_id))
    if path is None:
        raise HTTPException(404, "Final video is not ready.")
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "no-store"})
