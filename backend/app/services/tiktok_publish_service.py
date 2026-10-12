"""Private TikTok Direct Post of an existing, generated final.mp4."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse
from uuid import UUID

import httpx
from moviepy import VideoFileClip
from pydantic import ValidationError

from app.models.platform import PlatformResult
from app.services.output_language import load_output_language
from app.services.video_cache import cached_video_file
from app.services.tiktok_oauth_service import (
    TOKEN_FILE,
    TikTokOAuthError,
    has_publish_scope,
    refresh_access_token,
)


STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"
API_BASE = "https://open.tiktokapis.com/v2/post/publish"
PRIVACY = "SELF_ONLY"
MAX_SINGLE_CHUNK = 64 * 1024 * 1024
LARGE_CHUNK = 32 * 1024 * 1024
POLL_INTERVAL = 2.5
POLL_TIMEOUT = 90.0


class TikTokPublishError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _run_dir(run_id: UUID) -> Path:
    folder = STORAGE_DIR / str(run_id)
    if not folder.is_dir():
        raise TikTokPublishError("Document run was not found.", 404)
    return folder


def _video_file(folder: Path) -> tuple[Path, int]:
    video = cached_video_file(folder)
    if video is None:
        raise TikTokPublishError("Final video is not available for the selected language.", 404)
    try:
        size = video.stat().st_size
    except OSError as exc:
        raise TikTokPublishError("Final video is not available for this run.", 404) from exc
    if size <= 0:
        raise TikTokPublishError("Final video is not available for this run.", 404)
    return video, size


def _caption(folder: Path) -> str:
    path = folder / "platforms.json"
    try:
        saved = PlatformResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise TikTokPublishError("Saved TikTok caption is unavailable.", 422) from exc
    if "tiktok" not in saved.platforms or "video" not in saved.content_types:
        raise TikTokPublishError("TikTok was not selected for this run.", 409)
    if saved.language != load_output_language(folder):
        raise TikTokPublishError(
            "Saved TikTok language does not match this run. Generate the selected language first.",
            409,
        )
    post = next((item for item in saved.items if item.platform == "tiktok"), None)
    caption = (post.body or post.title).strip() if post else ""
    if not caption:
        raise TikTokPublishError("Saved TikTok caption is unavailable.", 422)
    if len(caption.encode("utf-16-le")) // 2 > 2200:
        raise TikTokPublishError("Saved TikTok caption exceeds the platform limit.", 422)
    return caption


def _video_duration(video: Path) -> float:
    try:
        with VideoFileClip(str(video), audio=False) as clip:
            duration = float(clip.duration)
        if duration <= 0:
            raise ValueError("Invalid duration")
        return duration
    except Exception as exc:
        raise TikTokPublishError("Final video duration could not be read.", 422) from exc


async def _access_token() -> str:
    try:
        saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        if not isinstance(saved, dict) or not saved.get("access_token"):
            raise TikTokPublishError("TikTok is not connected.", 401)
        if not saved.get("refresh_token"):
            raise TikTokPublishError("TikTok needs to be reconnected before publishing.", 401)
        if not has_publish_scope(saved.get("scope", "")):
            raise TikTokPublishError(
                "TikTok video publishing permission is missing. Please reconnect.", 403
            )
        expiry = datetime.fromisoformat(saved["expires_at"])
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    except FileNotFoundError as exc:
        raise TikTokPublishError("TikTok is not connected.", 401) from exc
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise TikTokPublishError(
            "TikTok connection could not be read. Please reconnect.", 401
        ) from exc

    if expiry <= datetime.now(timezone.utc) + timedelta(minutes=2):
        try:
            return await refresh_access_token()
        except TikTokOAuthError as exc:
            raise TikTokPublishError("TikTok token refresh failed. Please reconnect.", 401) from exc
    return saved["access_token"]


def _record_path(folder: Path) -> Path:
    language = load_output_language(folder)
    suffix = "" if language == "en" else f"_{language}"
    return folder / f"tiktok_publication{suffix}.json"


def load_record(folder: Path) -> dict | None:
    try:
        value = json.loads(_record_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("publish_id"), str)
        or not value["publish_id"]
        or value.get("privacy") != PRIVACY
    ):
        return None
    return value


def _save_record(folder: Path, record: dict) -> None:
    path = _record_path(folder)
    temporary = path.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(record), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise TikTokPublishError(
            "TikTok publishing state could not be saved. Check your account before retrying.", 503
        ) from exc


def _safe_result(record: dict) -> dict:
    status = record["status"]
    return {
        "success": status == "PUBLISH_COMPLETE",
        "platform": "tiktok",
        "publish_id": record["publish_id"],
        "status": status,
        "privacy": PRIVACY,
    }


def local_status(run_id: UUID) -> dict:
    record = load_record(_run_dir(run_id))
    return (
        _safe_result(record)
        if record
        else {"success": False, "platform": "tiktok", "status": "IDLE", "privacy": PRIVACY}
    )


def _api_error(code: str, stage: str) -> TikTokPublishError:
    if code in {"access_token_invalid", "scope_not_authorized"}:
        return TikTokPublishError(
            "TikTok authorization expired or lacks video publishing permission. Please reconnect.",
            401,
        )
    if code in {"rate_limit_exceeded", "spam_risk_too_many_posts", "reached_active_user_cap"}:
        return TikTokPublishError("TikTok posting limit reached. Please try again later.", 429)
    if code == "unaudited_client_can_only_post_to_private_accounts":
        return TikTokPublishError("This TikTok sandbox can post only to a private account.", 403)
    if code == "privacy_level_option_mismatch":
        return TikTokPublishError("Private posting is not available for this TikTok account.", 422)
    return TikTokPublishError(f"TikTok {stage} failed. Please retry.")


async def _post_json(
    client: httpx.AsyncClient, path: str, token: str, body: dict | None, stage: str
) -> dict:
    try:
        response = await client.post(
            f"{API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=body if body is not None else {},
        )
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise TikTokPublishError(f"TikTok {stage} timed out. Please retry.", 504) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise TikTokPublishError(f"TikTok {stage} could not be completed. Please retry.") from exc
    code = (
        payload.get("error", {}).get("code")
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict)
        else None
    )
    if not response.is_success and code == "ok":
        raise TikTokPublishError(f"TikTok {stage} failed. Please retry.")
    if code != "ok":
        raise _api_error(code or "", stage)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise TikTokPublishError(f"TikTok {stage} returned an incomplete response.")
    return data


def parse_creator_info(data: dict, duration: float) -> dict[str, bool]:
    options = data.get("privacy_level_options")
    if not isinstance(options, list) or PRIVACY not in options:
        raise TikTokPublishError("Private posting is not available for this TikTok account.", 422)
    maximum = data.get("max_video_post_duration_sec")
    if isinstance(maximum, bool) or not isinstance(maximum, (int, float)) or maximum <= 0:
        raise TikTokPublishError("TikTok did not provide a usable video duration limit.")
    if duration > maximum:
        raise TikTokPublishError("Final video exceeds this TikTok account's duration limit.", 422)
    flags = ("comment_disabled", "duet_disabled", "stitch_disabled")
    if any(type(data.get(flag)) is not bool for flag in flags):
        raise TikTokPublishError("TikTok did not provide complete interaction settings.")
    return {
        "disable_comment": data["comment_disabled"],
        "disable_duet": data["duet_disabled"],
        "disable_stitch": data["stitch_disabled"],
    }


def _chunks(size: int) -> tuple[int, int]:
    chunk_size = size if size <= MAX_SINGLE_CHUNK else LARGE_CHUNK
    count = max(1, size // chunk_size)
    if count > 1000:
        raise TikTokPublishError("Final video is too large for TikTok upload.", 422)
    return chunk_size, count


def _validate_upload_url(value: str) -> str:
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not host.endswith(".tiktokapis.com")
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise TikTokPublishError("TikTok returned an invalid upload destination.")
    return value


async def _upload(
    client: httpx.AsyncClient, url: str, video: Path, size: int, chunk_size: int, count: int
) -> None:
    with video.open("rb") as source:
        for index in range(count):
            start = index * chunk_size
            length = chunk_size if index < count - 1 else size - start
            content = source.read(length)
            if len(content) != length:
                raise TikTokPublishError("Final video changed during upload. Please retry.", 409)
            try:
                response = await client.put(
                    url,
                    content=content,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(length),
                        "Content-Range": f"bytes {start}-{start + length - 1}/{size}",
                    },
                    timeout=120,
                )
            except httpx.TimeoutException as exc:
                raise TikTokPublishError(
                    "TikTok upload timed out. Check status before retrying.", 504
                ) from exc
            except httpx.HTTPError as exc:
                raise TikTokPublishError(
                    "TikTok upload failed. Check status before retrying."
                ) from exc
            expected = 201 if index == count - 1 else 206
            if response.status_code != expected:
                raise TikTokPublishError("TikTok upload failed. Check status before retrying.")


def _failure_message(reason: str) -> str:
    if reason == "duration_check_failed":
        return "TikTok rejected the video duration."
    if reason == "file_format_check_failed":
        return "TikTok rejected the video format."
    if reason in {"auth_removed", "access_token_invalid"}:
        return "TikTok authorization was removed. Please reconnect."
    if reason.startswith("spam_risk"):
        return "TikTok rejected this post under its posting limits."
    return "TikTok publishing failed. Please retry."


async def _fetch_status(client: httpx.AsyncClient, token: str, folder: Path, record: dict) -> dict:
    data = await _post_json(
        client, "/status/fetch/", token, {"publish_id": record["publish_id"]}, "status check"
    )
    status = data.get("status")
    if status not in {"PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "PUBLISH_COMPLETE", "FAILED"}:
        raise TikTokPublishError("TikTok returned an unknown publishing status.")
    record = {**record, "status": status}
    _save_record(folder, record)
    if status == "FAILED":
        raise TikTokPublishError(_failure_message(str(data.get("fail_reason", ""))))
    return _safe_result(record)


async def check_publish_status(run_id: UUID) -> dict:
    folder = _run_dir(run_id)
    record = load_record(folder)
    if not record:
        raise TikTokPublishError("No TikTok post has been started for this run.", 404)
    if record["status"] == "PUBLISH_COMPLETE":
        return _safe_result(record)
    token = await _access_token()
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        try:
            return await _fetch_status(client, token, folder, record)
        except TikTokPublishError as exc:
            if (
                exc.status_code in (502, 504)
                and (load_record(folder) or {}).get("status") != "FAILED"
            ):
                return _safe_result(record)
            raise


async def publish_video(run_id: UUID) -> dict:
    folder = _run_dir(run_id)
    video, size = _video_file(folder)
    token = await _access_token()
    existing = load_record(folder)
    if existing:
        if existing["status"] == "PUBLISH_COMPLETE":
            return _safe_result(existing)
        if existing["status"] != "FAILED":
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                return await _fetch_status(client, token, folder, existing)

    caption = _caption(folder)
    duration = await asyncio.to_thread(_video_duration, video)
    chunk_size, count = _chunks(size)

    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        creator = await _post_json(client, "/creator_info/query/", token, None, "creator check")
        settings = parse_creator_info(creator, duration)
        initialized = await _post_json(
            client,
            "/video/init/",
            token,
            {
                "post_info": {
                    "title": caption,
                    "privacy_level": PRIVACY,
                    **settings,
                    "is_aigc": True,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": count,
                },
            },
            "post initialization",
        )
        publish_id = initialized.get("publish_id")
        upload_url = initialized.get("upload_url")
        if not isinstance(publish_id, str) or not publish_id or not isinstance(upload_url, str):
            raise TikTokPublishError("TikTok did not confirm the upload session.")
        upload_url = _validate_upload_url(upload_url)
        record = {"publish_id": publish_id, "status": "PROCESSING_UPLOAD", "privacy": PRIVACY}
        _save_record(folder, record)
        try:
            await _upload(client, upload_url, video, size, chunk_size, count)
        except TikTokPublishError:
            _save_record(folder, {**record, "status": "UPLOAD_FAILED"})
            raise

        deadline = monotonic() + POLL_TIMEOUT
        while True:
            try:
                result = await _fetch_status(client, token, folder, record)
            except TikTokPublishError as exc:
                if (
                    exc.status_code in (502, 504)
                    and (load_record(folder) or {}).get("status") != "FAILED"
                ):
                    return _safe_result(record)
                raise
            if result["success"]:
                return result
            if monotonic() >= deadline:
                return result
            await asyncio.sleep(POLL_INTERVAL)
