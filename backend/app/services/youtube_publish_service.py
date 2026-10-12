"""Publish an already rendered run video to the connected YouTube channel."""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from pydantic import ValidationError

from app.models.platform import PlatformResult
from app.services.output_language import load_output_language
from app.services.video_cache import cached_video_file


STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"
TOKEN_FILE = STORAGE_DIR / "auth" / "youtube.json"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TOKEN_URI = "https://oauth2.googleapis.com/token"
VIDEO_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{11}\Z")
LOGGER = logging.getLogger("uvicorn.error")


class YouTubePublishError(Exception):
    def __init__(self, message: str, status_code: int, diagnostics: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.diagnostics = diagnostics


def _safe_text(value: object, saved: dict | None = None) -> str:
    if not isinstance(value, str):
        return ""
    result = value
    secrets = [os.getenv("YOUTUBE_CLIENT_SECRET", "")]
    if saved:
        secrets.extend(
            (
                saved.get("access_token", ""),
                saved.get("refresh_token", ""),
                saved.get("new_access_token", ""),
            )
        )
    for secret in secrets:
        if isinstance(secret, str) and secret:
            result = result.replace(secret, "[redacted]")
    result = re.sub(r"https?://\S+", "[URL redacted]", result)
    result = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", result)
    result = re.sub(
        r"(?i)\b(?:access_token|refresh_token|client_secret|authorization)\s*[:=]\s*\S+",
        "[redacted]",
        result,
    )
    result = re.sub(r"[A-Za-z0-9_-]{40,}", "[redacted]", result)
    result = re.sub(r"[\x00-\x1f\x7f]+", " ", result)
    return result.strip()[:300]


def _safe_identifier(value: object) -> str:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", value):
        return value
    return ""


def parse_google_http_error(exc: HttpError, saved: dict | None = None) -> dict:
    """Return only diagnostic fields safe to log or expose to the local frontend."""
    diagnostics: dict = {"youtube_reason": "unknown_google_error"}
    try:
        diagnostics["youtube_status"] = int(exc.resp.status)
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        payload = json.loads(exc.content.decode("utf-8"))
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            raise ValueError("Invalid Google error body")
        details = error.get("errors")
        first = (
            details[0]
            if isinstance(details, list) and details and isinstance(details[0], dict)
            else {}
        )
        reason = _safe_identifier(first.get("reason"))
        domain = _safe_identifier(first.get("domain"))
        if not reason:
            more = error.get("details")
            info = (
                next(
                    (
                        item
                        for item in more
                        if isinstance(item, dict)
                        and item.get("@type", "").endswith("google.rpc.ErrorInfo")
                    ),
                    {},
                )
                if isinstance(more, list)
                else {}
            )
            reason = _safe_identifier(info.get("reason"))
            domain = domain or _safe_identifier(info.get("domain"))
        diagnostics["youtube_reason"] = reason or "unknown_google_error"
        if domain:
            diagnostics["youtube_domain"] = domain
        message = _safe_text(error.get("message") or first.get("message"), saved)
        if message:
            diagnostics["youtube_message"] = message
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError):
        pass
    return diagnostics


def _log_non_http_error(exc: Exception, saved: dict | None = None) -> None:
    LOGGER.error(
        "[YouTube] publish failed: exception=%s message=%s",
        type(exc).__name__,
        _safe_text(str(exc), saved) or "No safe message available.",
    )


def _read_tokens() -> dict:
    try:
        saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise YouTubePublishError("YouTube is not connected.", 401) from exc
    except (OSError, ValueError) as exc:
        raise YouTubePublishError(
            "YouTube connection could not be read. Please reconnect.", 401
        ) from exc
    if (
        not isinstance(saved, dict)
        or not saved.get("access_token")
        or SCOPE not in str(saved.get("scope", "")).split()
    ):
        raise YouTubePublishError("YouTube is not connected.", 401)
    if not saved.get("refresh_token"):
        raise YouTubePublishError("YouTube needs to be reconnected before publishing.", 401)
    return saved


def _credentials(saved: dict) -> Credentials:
    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise YouTubePublishError("YouTube publishing is not configured.", 503)

    credentials = Credentials(
        token=saved["access_token"],
        refresh_token=saved["refresh_token"],
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[SCOPE],
    )
    try:
        expiry = datetime.fromisoformat(saved["expires_at"].replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    except (KeyError, AttributeError, TypeError, ValueError):
        expiry = datetime.min.replace(tzinfo=timezone.utc)

    if expiry <= datetime.now(timezone.utc) + timedelta(minutes=2):
        LOGGER.info("[YouTube] refreshing token")
        try:
            credentials.refresh(GoogleRequest())
        except (GoogleAuthError, OSError) as exc:
            _log_non_http_error(exc, saved)
            raise YouTubePublishError(
                "YouTube token refresh failed. Please reconnect and retry.", 401
            ) from exc
        if not credentials.token or not credentials.expiry:
            raise YouTubePublishError(
                "YouTube token refresh failed. Please reconnect and retry.", 401
            )
        refreshed = {
            **saved,
            "access_token": credentials.token,
            "expires_at": credentials.expiry.replace(tzinfo=timezone.utc).isoformat(),
            "refresh_token": saved["refresh_token"],
        }
        temporary = TOKEN_FILE.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(refreshed), encoding="utf-8")
            temporary.replace(TOKEN_FILE)
        except OSError as exc:
            raise YouTubePublishError(
                "YouTube credentials could not be saved. Please retry.", 503
            ) from exc
    return credentials


def _publication_path(run_dir: Path) -> Path:
    language = load_output_language(run_dir)
    suffix = "" if language == "en" else f"_{language}"
    return run_dir / f"youtube_publication{suffix}.json"


def load_publication(run_dir: Path) -> dict | None:
    try:
        saved = json.loads(_publication_path(run_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    video_id = saved.get("video_id") if isinstance(saved, dict) else None
    if not isinstance(video_id, str) or not VIDEO_ID_PATTERN.fullmatch(video_id):
        return None
    return {
        "success": True,
        "video_id": video_id,
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "privacy_status": "private",
    }


def _metadata(
    run_dir: Path, fallback_title: str | None, fallback_description: str | None
) -> tuple[str, str]:
    saved_title = ""
    saved_description = ""
    path = run_dir / "platforms.json"
    if path.is_file():
        try:
            platforms = PlatformResult.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            raise YouTubePublishError("Saved YouTube content could not be read.", 422) from exc
        if "youtube" not in platforms.platforms:
            raise YouTubePublishError("YouTube was not selected for this run.", 409)
        if platforms.language != load_output_language(run_dir):
            raise YouTubePublishError(
                "Saved YouTube language does not match this run. Generate the selected language first.",
                409,
            )
        post = next((item for item in platforms.items if item.platform == "youtube"), None)
        if post:
            saved_title, saved_description = post.title, post.body

    title = (saved_title or fallback_title or "").strip()
    description = (saved_description or fallback_description or "").strip()
    if not title or not description:
        raise YouTubePublishError("YouTube title and description are required.", 422)
    title = title[:100].strip()
    if "<" in title or ">" in title:
        raise YouTubePublishError("YouTube title contains unsupported characters.", 422)
    return title, description


def publish_video(
    run_id: UUID, fallback_title: str | None, fallback_description: str | None
) -> dict:
    LOGGER.info("[YouTube] locating final.mp4")
    run_dir = STORAGE_DIR / str(run_id)
    if not run_dir.is_dir():
        raise YouTubePublishError("Document run was not found.", 404)
    video = cached_video_file(run_dir)
    try:
        video_ready = video is not None and video.is_file() and video.stat().st_size > 0
    except OSError:
        video_ready = False
    if not video_ready:
        raise YouTubePublishError("Final video is not available for this run.", 404)

    LOGGER.info("[YouTube] loading credentials")
    saved_tokens = _read_tokens()
    existing = load_publication(run_dir)
    if existing:
        return existing
    LOGGER.info("[YouTube] preparing metadata")
    title, description = _metadata(run_dir, fallback_title, fallback_description)
    credentials = _credentials(saved_tokens)
    log_redactions = {**saved_tokens, "new_access_token": credentials.token}

    try:
        LOGGER.info("[YouTube] creating videos.insert request")
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        media = MediaFileUpload(
            str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        )
        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description, "categoryId": "28"},
                "status": {"privacyStatus": "private"},
            },
            media_body=media,
        )
        LOGGER.info("[YouTube] starting upload")
        response = None
        while response is None:
            _, response = request.next_chunk(num_retries=2)
    except HttpError as exc:
        diagnostics = parse_google_http_error(exc, log_redactions)
        LOGGER.error(
            "[YouTube] publish failed: status=%s reason=%s domain=%s message=%s",
            diagnostics.get("youtube_status", "unknown"),
            diagnostics["youtube_reason"],
            diagnostics.get("youtube_domain", "unknown"),
            diagnostics.get("youtube_message", "No safe Google message available."),
        )
        raise YouTubePublishError("YouTube publishing failed.", 502, diagnostics) from exc
    except (GoogleAuthError, OSError) as exc:
        _log_non_http_error(exc, log_redactions)
        raise YouTubePublishError("YouTube upload failed. Please retry.", 502) from exc
    except Exception as exc:
        _log_non_http_error(exc, log_redactions)
        raise YouTubePublishError("YouTube upload failed. Please retry.", 502) from exc

    video_id = response.get("id") if isinstance(response, dict) else None
    if not isinstance(video_id, str) or not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise YouTubePublishError(
            "YouTube did not confirm the uploaded video. Please check your channel.", 502
        )
    LOGGER.info("[YouTube] upload completed")

    publication = {
        "success": True,
        "video_id": video_id,
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "privacy_status": "private",
    }
    temporary = _publication_path(run_dir).with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(publication), encoding="utf-8")
        temporary.replace(_publication_path(run_dir))
    except OSError as exc:
        raise YouTubePublishError(
            "Video uploaded, but its result could not be saved. Check your channel before retrying.",
            503,
        ) from exc
    return publication
