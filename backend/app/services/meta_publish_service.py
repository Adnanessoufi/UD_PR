"""Publish saved platform copy and the selected media to Meta accounts."""

import asyncio
from fractions import Fraction
from hashlib import sha256
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlparse, urlsplit
from uuid import UUID

import httpx
from dotenv import load_dotenv
import imageio_ffmpeg
from PIL import Image, ImageCms, ImageOps
from pydantic import ValidationError

from app.models.assets import AssetPack
from app.models.platform import PlatformResult
from app.services.output_language import load_output_language
from app.services.video_cache import cached_video_file
from app.services.video_service import load_uploads


load_dotenv(Path(__file__).resolve().parents[2] / ".env")
STORAGE = Path(__file__).resolve().parents[2] / "storage"
LOG = logging.getLogger(__name__)


class MetaPublishError(Exception):
    def __init__(self, message: str, status_code: int = 502, details: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


def connection_status() -> dict:
    token = bool(os.getenv("META_PAGE_ACCESS_TOKEN", "").strip())
    return {
        "facebook_connected": token and bool(os.getenv("META_PAGE_ID", "").strip()),
        "instagram_connected": token and bool(os.getenv("META_INSTAGRAM_ACCOUNT_ID", "").strip()),
    }


def _configuration(platform: str) -> tuple[str, str, str]:
    account = os.getenv(
        "META_PAGE_ID" if platform == "facebook" else "META_INSTAGRAM_ACCOUNT_ID", ""
    ).strip()
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    version = os.getenv("META_GRAPH_VERSION", "v26.0").strip()
    if not account or not token:
        raise MetaPublishError(
            f"{platform.title()} publishing is not configured on the backend.", 503
        )
    if not account.isdecimal() or not re.fullmatch(r"v\d+\.\d+", version):
        raise MetaPublishError("Meta account ID or Graph API version is invalid.", 503)
    return account, token, f"https://graph.facebook.com/{version}"


def _folder(run_id: UUID) -> Path:
    folder = STORAGE / str(run_id)
    if not folder.is_dir():
        raise MetaPublishError("Document run was not found.", 404)
    return folder


def _copy(folder: Path, platform: str) -> str:
    try:
        result = PlatformResult.model_validate_json(
            (folder / "platforms.json").read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise MetaPublishError("Saved platform content is unavailable.", 422) from exc
    if platform not in result.platforms:
        raise MetaPublishError(f"{platform.title()} was not selected for this run.", 409)
    if result.language != load_output_language(folder):
        raise MetaPublishError(
            "Saved platform language does not match this run. Generate the selected language first.",
            409,
        )
    post = next((item for item in result.items if item.platform == platform), None)
    caption = (post.body or post.title).strip() if post else ""
    if not caption:
        raise MetaPublishError(f"Saved {platform.title()} text is unavailable.", 422)
    return caption


def _media(folder: Path, primary_media_id: str | None) -> tuple[str, Path, str] | None:
    if not primary_media_id:
        return None
    run_id = folder.name
    if primary_media_id == "generated_video":
        path = cached_video_file(folder)
        if path is None:
            raise MetaPublishError("Final video is unavailable for the selected language.", 404)
        route = f"/api/video/{run_id}/file"
        kind = "video"
    elif primary_media_id.startswith("uploaded_video:"):
        clip_id = primary_media_id.removeprefix("uploaded_video:")
        try:
            uploads = load_uploads(folder)
        except (OSError, ValueError, TypeError) as exc:
            raise MetaPublishError("Saved video uploads could not be read.", 422) from exc
        clip = next(
            (item for item in uploads if isinstance(item, dict) and item.get("id") == clip_id), None
        )
        filename = clip.get("filename", "") if clip else ""
        if not re.fullmatch(r"[0-9a-f]{32}\.(mp4|mov|webm)", filename):
            raise MetaPublishError("Selected video is unavailable.", 404)
        path = folder / "video" / "uploads" / filename
        route = f"/api/video/{run_id}/uploads/{filename}"
        kind = "video"
    else:
        try:
            pack = AssetPack.model_validate_json(
                (folder / "assets.json").read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise MetaPublishError("Saved image assets are unavailable.", 422) from exc
        asset = next((item for item in pack.assets if item.id == primary_media_id), None)
        if not asset:
            raise MetaPublishError("Selected image is unavailable.", 404)
        if asset.type == "user_upload":
            expected = re.fullmatch(
                rf"/api/assets/{run_id}/files/uploads/([0-9a-f]{{32}}\.(?:png|jpg|webp))",
                asset.path.split("?", 1)[0],
            )
            if not expected:
                raise MetaPublishError("Saved image path is invalid.", 422)
            filename = expected.group(1)
            path = folder / "assets" / "uploads" / filename
            route = f"/api/assets/{run_id}/files/uploads/{filename}"
        else:
            filename = f"{asset.type}.png"
            if asset.path.split("?", 1)[0] != f"/api/assets/{run_id}/files/{filename}":
                raise MetaPublishError("Saved image path is invalid.", 422)
            path = folder / "assets" / filename
            route = f"/api/assets/{run_id}/files/{filename}"
        kind = "image"
    if not path.is_file() or path.stat().st_size == 0:
        raise MetaPublishError("Selected media file is unavailable.", 404)
    return kind, path, route


def public_media_url(route: str, base: str | None = None) -> str:
    value = (base if base is not None else os.getenv("PUBLIC_BACKEND_URL", "")).strip()
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise MetaPublishError(
            "Set PUBLIC_BACKEND_URL to the current public HTTPS backend URL before publishing to Instagram.",
            503,
        )
    if (
        not route.startswith("/api/assets/")
        and not route.startswith("/api/video/")
        and not re.fullmatch(r"/api/meta/media/[0-9a-f-]{36}/(?:[^/]+\.jpg|instagram\.mp4)", route)
    ):
        raise MetaPublishError("Selected public media route is invalid.", 422)
    return value.rstrip("/") + route


def resolve_public_media_url(
    run_id: UUID, primary_media_id: str | None, base: str | None = None
) -> tuple[str, Path, str]:
    """Resolve a saved primary ID to its existing, run-owned public media route."""
    asset_type = (
        "generated_video"
        if primary_media_id == "generated_video"
        else "uploaded_video"
        if primary_media_id and primary_media_id.startswith("uploaded_video:")
        else "user_upload"
        if primary_media_id and primary_media_id.startswith("upload_")
        else primary_media_id
        if primary_media_id
        in {
            "generated_explainer",
            "generated_education_visual",
            "source_visual",
            "publication_preview",
            "programme_card",
        }
        else "unknown"
    )
    media_type = (
        "video"
        if asset_type in {"generated_video", "uploaded_video"}
        else "image"
        if asset_type != "unknown"
        else "unknown"
    )
    details = {"media_type": media_type, "asset_type": asset_type}
    try:
        media = _require_instagram_media(_media(_folder(run_id), primary_media_id))
        kind, path, saved_route = media
        details["media_type"] = kind
        parsed = urlsplit(saved_route)
        route = parsed.path
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise MetaPublishError("Selected public media route is invalid.", 422)
        run = re.escape(str(run_id))
        allowed = (
            re.fullmatch(
                rf"/api/assets/{run}/files/(?:generated_explainer|generated_education_visual|source_visual|publication_preview|programme_card)\.png",
                route,
            )
            or re.fullmatch(
                rf"/api/assets/{run}/files/uploads/[0-9a-f]{{32}}\.(?:png|jpg|webp)", route
            )
            or re.fullmatch(rf"/api/video/{run}/file", route)
            or re.fullmatch(rf"/api/video/{run}/uploads/[0-9a-f]{{32}}\.(?:mp4|mov|webm)", route)
        )
        if not allowed or not path.is_file() or path.stat().st_size <= 0:
            raise MetaPublishError("Selected public media route is invalid.", 422)
        details["resolved_route"] = route
        print(f"[Meta][Instagram] primary media type={kind}", flush=True)
        print(f"[Meta][Instagram] asset type={asset_type}", flush=True)
        print(f"[Meta][Instagram] resolved route={route}", flush=True)
        url = public_media_url(route, base)
        print("[Meta][Instagram] public URL constructed", flush=True)
        return kind, path, url
    except MetaPublishError as exc:
        raise MetaPublishError(str(exc), exc.status_code, {**details, **exc.details}) from exc


def _require_instagram_media(media: tuple[str, Path, str] | None) -> tuple[str, Path, str]:
    if media is None:
        raise MetaPublishError("Instagram requires a primary image or video.", 422)
    return media


def _safe_message(value: object, token: str) -> str:
    message = str(value)[:300] if value is not None else "Meta rejected the request."
    if token:
        message = message.replace(token, "[redacted]")
    message = re.sub(
        r"(?i)(access_token|authorization|client_secret|refresh_token)\s*[:=]\s*[^\s&]+",
        r"\1=[redacted]",
        message,
    )
    return message


def _graph_result(response: httpx.Response, token: str, stage: str) -> dict:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if response.is_success and isinstance(payload, dict) and not payload.get("error"):
        return payload
    error = payload.get("error") if isinstance(payload, dict) else None
    error = error if isinstance(error, dict) else {}
    details = {"meta_status": response.status_code}
    for key, output in (
        ("code", "meta_code"),
        ("error_subcode", "meta_subcode"),
        ("type", "meta_type"),
    ):
        value = error.get(key)
        if isinstance(value, (int, str)) and not isinstance(value, bool):
            details[output] = value if isinstance(value, int) else _safe_message(value, token)
    details["meta_message"] = _safe_message(error.get("message"), token)
    LOG.warning(
        "[Meta] %s failed: status=%s code=%s subcode=%s type=%s message=%s",
        stage,
        details["meta_status"],
        details.get("meta_code"),
        details.get("meta_subcode"),
        details.get("meta_type"),
        details["meta_message"],
    )
    raise MetaPublishError(f"Meta {stage} failed.", 502, details)


async def _request(
    client: httpx.AsyncClient, method: str, url: str, token: str, stage: str, **kwargs
) -> dict:
    try:
        response = await client.request(
            method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs
        )
    except httpx.TimeoutException as exc:
        raise MetaPublishError(
            f"Meta {stage} timed out. Check the account before retrying.", 504
        ) from exc
    except httpx.HTTPError as exc:
        raise MetaPublishError(f"Meta {stage} could not be completed.", 502) from exc
    return _graph_result(response, token, stage)


def _record_path(folder: Path, platform: str) -> Path:
    language = load_output_language(folder)
    # The original unqualified record belongs to English runs.
    suffix = "" if language == "en" else f"_{language}"
    return folder / f"{platform}_publication{suffix}.json"


def _read_record(folder: Path, platform: str) -> dict | None:
    try:
        record = json.loads(_record_path(folder, platform).read_text(encoding="utf-8"))
        return (
            record
            if isinstance(record, dict) and record.get("status") in {"PROCESSING", "PUBLISHED"}
            else None
        )
    except (OSError, ValueError):
        return None


def _save_record(folder: Path, platform: str, record: dict) -> None:
    path = _record_path(folder, platform)
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(record), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        raise MetaPublishError(
            "Publishing state could not be saved. Check the account before retrying.", 503
        ) from exc


def _safe_publication_url(platform: str, value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    allowed = (
        {"facebook.com", "www.facebook.com"}
        if platform == "facebook"
        else {"instagram.com", "www.instagram.com"}
    )
    if parsed.scheme != "https" or parsed.netloc not in allowed or not parsed.path.startswith("/"):
        return None
    return value


async def publication_status(run_id: UUID, platform: str) -> dict:
    record = _read_record(_folder(run_id), platform)
    if record:
        if record["status"] == "PUBLISHED" and not _safe_publication_url(
            platform, record.get("publication_url")
        ):
            record.pop("publication_url", None)
            media_id = record.get("post_id" if platform == "facebook" else "media_id")
            # A Facebook Page post ID is already a usable post URL. Instagram media IDs
            # are not shortcodes, so its real permalink must come from Graph.
            if (
                platform == "facebook"
                and isinstance(media_id, str)
                and re.fullmatch(r"\d+_\d+", media_id)
            ):
                record["publication_url"] = f"https://www.facebook.com/{media_id}"
            elif isinstance(media_id, str) and re.fullmatch(r"\d+", media_id):
                fields = (
                    ("link", "permalink_url")
                    if platform == "facebook" and record.get("media_kind") == "image"
                    else (("permalink_url", "link") if platform == "facebook" else ("permalink",))
                )
                for field in fields:
                    try:
                        _, token, graph = _configuration(platform)
                        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                            result = await _request(
                                client,
                                "GET",
                                f"{graph}/{media_id}",
                                token,
                                "publication link lookup",
                                params={"fields": field},
                            )
                        record["publication_url"] = _safe_publication_url(
                            platform, result.get(field)
                        )
                        if record["publication_url"]:
                            break
                    except MetaPublishError as exc:
                        # The post stays published even if Meta can no longer resolve its link.
                        if platform == "instagram" and exc.details.get("meta_code") == 190:
                            record["publication_link_error"] = (
                                "Instagram link unavailable: Meta access token expired."
                            )
                        elif platform == "instagram":
                            record["publication_link_error"] = (
                                "Instagram link unavailable. Check the Meta connection."
                            )
                if platform == "facebook" and not record.get("publication_url"):
                    if record.get("media_kind") == "video":
                        record["publication_url"] = f"https://www.facebook.com/watch/?v={media_id}"
                    elif record.get("media_kind") in {"image", None}:
                        record["publication_url"] = (
                            f"https://www.facebook.com/photo/?fbid={media_id}"
                        )
            if record.get("publication_url"):
                try:
                    _save_record(_folder(run_id), platform, record)
                except MetaPublishError:
                    pass  # The published post and its link remain valid in this response.
        return {"success": record["status"] == "PUBLISHED", "platform": platform, **record}
    return {"success": False, "platform": platform, "status": "IDLE"}


async def publish_facebook(run_id: UUID, primary_media_id: str | None) -> dict:
    account, token, graph = _configuration("facebook")
    folder = _folder(run_id)
    existing = _read_record(folder, "facebook")
    if existing and existing["status"] == "PUBLISHED":
        return {"success": True, "platform": "facebook", **existing}
    LOG.info("[Meta][Facebook] preparing post")
    caption = _copy(folder, "facebook")
    media = _media(folder, primary_media_id)
    async with httpx.AsyncClient(timeout=180, follow_redirects=False) as client:
        if media is None:
            result = await _request(
                client,
                "POST",
                f"{graph}/{account}/feed",
                token,
                "Facebook feed publish",
                data={"message": caption},
            )
        elif media[0] == "image":
            with media[1].open("rb") as source:
                result = await _request(
                    client,
                    "POST",
                    f"{graph}/{account}/photos",
                    token,
                    "Facebook photo publish",
                    data={"caption": caption},
                    files={"source": (media[1].name, source)},
                )
        else:
            if media[1].suffix.lower() != ".mp4":
                raise MetaPublishError(
                    "Facebook video publishing requires an MP4 primary video.", 422
                )
            with media[1].open("rb") as source:
                result = await _request(
                    client,
                    "POST",
                    f"https://graph-video.facebook.com/{os.getenv('META_GRAPH_VERSION', 'v26.0').strip()}/{account}/videos",
                    token,
                    "Facebook video publish",
                    data={"description": caption},
                    files={"source": (media[1].name, source, "video/mp4")},
                )
    post_id = result.get("post_id") or result.get("id")
    if not isinstance(post_id, str) or not post_id:
        raise MetaPublishError("Facebook did not return a post ID. Check the Page before retrying.")
    record = {
        "status": "PUBLISHED",
        "post_id": post_id,
        "media_kind": media[0] if media else "text",
    }
    _save_record(folder, "facebook", record)
    LOG.info("[Meta][Facebook] publish complete")
    return {"success": True, "platform": "facebook", **record}


async def _finish_instagram(
    client: httpx.AsyncClient, folder: Path, account: str, token: str, graph: str, record: dict
) -> dict:
    container_id = record["container_id"]
    LOG.info("[Meta][Instagram] waiting for media")
    status = await _request(
        client,
        "GET",
        f"{graph}/{container_id}",
        token,
        "Instagram media status",
        params={"fields": "status_code,status"},
    )
    code = status.get("status_code")
    if code in {"ERROR", "EXPIRED"}:
        details = {
            "container_id": container_id,
            "status_code": code,
            "status": _safe_message(status.get("status"), token)
            if status.get("status") is not None
            else None,
        }
        LOG.warning(
            "[Meta][Instagram] media processing failed: container_id=%s status_code=%s status=%s",
            details["container_id"],
            details["status_code"],
            details["status"],
        )
        _record_path(folder, "instagram").unlink(missing_ok=True)
        raise MetaPublishError(f"Instagram media processing {str(code).lower()}.", 502, details)
    if code == "IN_PROGRESS":
        return {"success": False, "platform": "instagram", "status": "PROCESSING"}
    if code != "FINISHED":
        raise MetaPublishError("Instagram returned an unknown media processing status.")
    LOG.info("[Meta][Instagram] publishing container")
    result = await _request(
        client,
        "POST",
        f"{graph}/{account}/media_publish",
        token,
        "Instagram media publish",
        data={"creation_id": container_id},
    )
    media_id = result.get("id")
    if not isinstance(media_id, str) or not media_id:
        raise MetaPublishError(
            "Instagram did not return a media ID. Check the account before retrying."
        )
    published = {"status": "PUBLISHED", "media_id": media_id}
    _save_record(folder, "instagram", published)
    LOG.info("[Meta][Instagram] publish complete")
    return {"success": True, "platform": "instagram", **published}


async def _verify_instagram_image_url(
    client: httpx.AsyncClient, url: str, expected_path: Path
) -> None:
    """Check that the public URL delivers the complete selected JPEG."""
    try:
        probe_headers = {"X-UD-Instagram-Preflight": "1"}
        head = await client.head(url, headers=probe_headers, follow_redirects=False)
        head_type = head.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if head.status_code != 200 or head_type != "image/jpeg":
            raise MetaPublishError(
                "Instagram public image URL must support HEAD with HTTP 200 and image/jpeg.",
                422,
                {"image_url_status": head.status_code, "image_url_content_type": head_type},
            )
        async with client.stream(
            "GET", url, headers=probe_headers, follow_redirects=False
        ) as response:
            content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if response.status_code != 200 or content_type != "image/jpeg":
                raise MetaPublishError(
                    "Instagram public image URL must return HTTP 200 and image/jpeg.",
                    422,
                    {
                        "image_url_status": response.status_code,
                        "image_url_content_type": content_type,
                    },
                )
            downloaded = sha256()
            downloaded_size = 0
            async for chunk in response.aiter_bytes():
                downloaded.update(chunk)
                downloaded_size += len(chunk)
        expected = sha256()
        with expected_path.open("rb") as source:
            for chunk in iter(lambda: source.read(64 * 1024), b""):
                expected.update(chunk)
        if (
            downloaded_size != expected_path.stat().st_size
            or downloaded.digest() != expected.digest()
        ):
            raise MetaPublishError(
                "Instagram public image URL returned incomplete or different JPEG data.", 502
            )
    except httpx.HTTPError as exc:
        raise MetaPublishError("Instagram public image URL could not be reached.", 502) from exc


def _probe_instagram_video(path: Path) -> dict:
    """Prefer ffprobe JSON; use the bundled FFmpeg stream report if absent."""
    probe = os.getenv("FFPROBE_BINARY", "").strip() or shutil.which("ffprobe")
    try:
        if probe:
            command = [
                probe,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise MetaPublishError("Instagram video could not be inspected with ffprobe.", 422)
            report = json.loads(result.stdout)
            streams = report.get("streams", [])
            video = next((item for item in streams if item.get("codec_type") == "video"), None)
            audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
            if video is None:
                raise MetaPublishError("Instagram video has no video stream.", 422)

            def number(value: object) -> int | None:
                return (
                    int(value) if isinstance(value, (int, str)) and str(value).isdigit() else None
                )

            rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0"
            fps = float(Fraction(rate)) if rate != "0/0" else 0.0
            return {
                "codec": video.get("codec_name"),
                "pixel_format": video.get("pix_fmt"),
                "width": number(video.get("width")),
                "height": number(video.get("height")),
                "fps": fps,
                "video_bitrate": number(video.get("bit_rate")),
                "audio_codec": audio.get("codec_name") if audio else None,
                "audio_sample_rate": number(audio.get("sample_rate")) if audio else None,
                "duration": float(
                    report.get("format", {}).get("duration") or video.get("duration") or 0
                ),
                "file_size": path.stat().st_size,
            }
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=30
        )
        info = result.stderr
        video_line = next((line for line in info.splitlines() if "Video:" in line), "")
        audio_line = next((line for line in info.splitlines() if "Audio:" in line), "")
        if not video_line:
            raise MetaPublishError("Instagram video has no video stream.", 422)
        dimensions = re.search(r"\b(\d{2,5})x(\d{2,5})\b", video_line)
        duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", info)
        bitrate = re.search(r",\s*(\d+)\s*kb/s", video_line)
        fps = re.search(r"(\d+(?:\.\d+)?)\s*fps", video_line)
        sample_rate = re.search(r"(\d+)\s*Hz", audio_line)
        return {
            "codec": re.search(r"Video:\s*([^\s,]+)", video_line).group(1),
            "pixel_format": "yuv420p" if "yuv420p" in video_line else None,
            "width": int(dimensions.group(1)) if dimensions else None,
            "height": int(dimensions.group(2)) if dimensions else None,
            "fps": float(fps.group(1)) if fps else 0.0,
            "video_bitrate": int(bitrate.group(1)) * 1000 if bitrate else None,
            "audio_codec": re.search(r"Audio:\s*([^\s,]+)", audio_line).group(1)
            if audio_line
            else None,
            "audio_sample_rate": int(sample_rate.group(1)) if sample_rate else None,
            "duration": int(duration.group(1)) * 3600
            + int(duration.group(2)) * 60
            + float(duration.group(3))
            if duration
            else 0.0,
            "file_size": path.stat().st_size,
        }
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise MetaPublishError("Instagram video could not be inspected.", 422) from exc


def _log_instagram_video(stage: str, info: dict) -> None:
    LOG.info(
        "[Meta][Instagram] %s codec=%s width=%s height=%s fps=%s video_bitrate=%s "
        "audio_codec=%s audio_sample_rate=%s duration=%s file_size=%s",
        stage,
        info["codec"],
        info["width"],
        info["height"],
        info["fps"],
        info["video_bitrate"],
        info["audio_codec"],
        info["audio_sample_rate"],
        info["duration"],
        info["file_size"],
    )


def instagram_video_file(run_id: UUID) -> Path:
    path = _folder(run_id) / "video" / "instagram_v1.mp4"
    if not path.is_file() or path.stat().st_size == 0:
        raise MetaPublishError("Instagram video is not ready.", 404)
    return path


def _prepare_instagram_video(run_id: UUID, source: Path) -> Path:
    original = _probe_instagram_video(source)
    _log_instagram_video("source video", original)
    width, height = original["width"], original["height"]
    if not width or not height or original["duration"] <= 0:
        raise MetaPublishError("Instagram video dimensions or duration are invalid.", 422)
    output = _folder(run_id) / "video" / "instagram_v1.mp4"
    if (
        output.is_file()
        and output.stat().st_size
        and output.stat().st_mtime_ns >= source.stat().st_mtime_ns
    ):
        _log_instagram_video("compatible video", _probe_instagram_video(output))
        return output
    scale = min(1.0, 1920 / width, 1920 / height)
    target_width = max(2, int(width * scale) // 2 * 2)
    target_height = max(2, int(height * scale) // 2 * 2)
    temporary = output.with_name("instagram_v1.tmp.mp4")
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
    ]
    if original["audio_codec"] is None:
        command += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    command += ["-map", "0:v:0", "-map", "0:a:0" if original["audio_codec"] else "1:a:0"]
    command += [
        "-vf",
        f"scale={target_width}:{target_height}:flags=lanczos,fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "22",
        "-maxrate",
        "8M",
        "-bufsize",
        "16M",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
    ]
    if original["audio_codec"] is None:
        command.append("-shortest")
    command += ["-f", "mp4", str(temporary)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=300)
        if result.returncode != 0 or not temporary.is_file():
            raise MetaPublishError("Instagram-compatible video encoding failed.", 502)
        compatible = _probe_instagram_video(temporary)
        if (
            compatible["codec"] != "h264"
            or compatible["pixel_format"] != "yuv420p"
            or compatible["audio_codec"] != "aac"
            or compatible["audio_sample_rate"] != 48000
            or not 29.9 <= compatible["fps"] <= 30.1
            or not compatible["width"]
            or compatible["width"] > 1920
            or not compatible["height"]
            or compatible["height"] > 1920
            or compatible["video_bitrate"] is not None
            and compatible["video_bitrate"] >= 25_000_000
        ):
            raise MetaPublishError(
                "Instagram-compatible video did not meet the required format.", 422
            )
        temporary.replace(output)
        _log_instagram_video("compatible video", compatible)
        return output
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MetaPublishError("Instagram-compatible video encoding failed.", 502) from exc
    finally:
        temporary.unlink(missing_ok=True)


async def _verify_instagram_video_url(client: httpx.AsyncClient, url: str, path: Path) -> None:
    try:
        response = await client.head(
            url, headers={"X-UD-Instagram-Preflight": "1"}, follow_redirects=False
        )
    except httpx.HTTPError as exc:
        raise MetaPublishError("Instagram public video URL could not be reached.", 502) from exc
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    content_length = response.headers.get("content-length")
    if (
        response.status_code != 200
        or content_type != "video/mp4"
        or (content_length is not None and content_length != str(path.stat().st_size))
    ):
        raise MetaPublishError(
            "Instagram public video URL must return the complete MP4 metadata.",
            422,
            {"video_url_status": response.status_code, "video_url_content_type": content_type},
        )


async def publish_instagram(run_id: UUID, primary_media_id: str | None) -> dict:
    account, token, graph = _configuration("instagram")
    folder = _folder(run_id)
    existing = _read_record(folder, "instagram")
    if existing and existing["status"] == "PUBLISHED":
        return {"success": True, "platform": "instagram", **existing}
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        if existing:
            return await _finish_instagram(client, folder, account, token, graph, existing)
        caption = _copy(folder, "instagram")
        kind, path, url = resolve_public_media_url(run_id, primary_media_id)
        if kind == "video" and path.suffix.lower() != ".mp4":
            raise MetaPublishError("Instagram Reel publishing requires an MP4 primary video.", 422)
        if kind == "image":
            if primary_media_id is None:
                raise MetaPublishError("Instagram requires a primary image.", 422)
            jpeg = instagram_jpeg_path(run_id, primary_media_id)
            url = public_media_url(f"/api/meta/media/{run_id}/{primary_media_id}.jpg")
        else:
            compatible_video = await asyncio.to_thread(_prepare_instagram_video, run_id, path)
            url = public_media_url(f"/api/meta/media/{run_id}/instagram.mp4")
        LOG.info("[Meta][Instagram] creating container")
        if kind == "image":
            with Image.open(jpeg) as normalized:
                width, height = normalized.size
            LOG.info(
                "[Meta][Instagram] image width=%s height=%s bytes=%s mime=image/jpeg image_url=%s",
                width,
                height,
                jpeg.stat().st_size,
                url,
            )
            await _verify_instagram_image_url(client, url, jpeg)
            data = {"image_url": url, "caption": caption}
        else:
            LOG.info("[Meta][Instagram] video_url=%s", url)
            await _verify_instagram_video_url(client, url, compatible_video)
            data = {"media_type": "REELS", "video_url": url, "caption": caption}
        result = await _request(
            client,
            "POST",
            f"{graph}/{account}/media",
            token,
            "Instagram container creation",
            data=data,
        )
        container_id = result.get("id")
        if not isinstance(container_id, str) or not container_id:
            raise MetaPublishError("Instagram did not return a media container ID.")
        record = {"status": "PROCESSING", "container_id": container_id}
        _save_record(folder, "instagram", record)
        return await _finish_instagram(client, folder, account, token, graph, record)


def instagram_jpeg_path(run_id: UUID, asset_id: str) -> Path:
    """Keep a normalized, run-owned JPEG copy available for Instagram's fetch."""
    media = _media(_folder(run_id), asset_id)
    if media is None or media[0] != "image":
        raise MetaPublishError("Image asset was not found.", 404)
    source_path = media[1]
    destination_dir = _folder(run_id) / "assets" / "instagram"
    destination = (
        destination_dir / f"{sha256(('feed-v2:' + asset_id).encode('utf-8')).hexdigest()}.jpg"
    )
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        if (
            destination.is_file()
            and destination.stat().st_mtime_ns >= source_path.stat().st_mtime_ns
        ):
            return destination
        with Image.open(source_path) as source:
            oriented = ImageOps.exif_transpose(source)
            rgba = oriented.convert("RGBA")
            color_source = oriented if oriented.mode in {"RGB", "CMYK"} else oriented.convert("RGB")
            profile = source.info.get("icc_profile")
            if profile:
                try:
                    colors = ImageCms.profileToProfile(
                        color_source,
                        ImageCms.ImageCmsProfile(BytesIO(profile)),
                        ImageCms.createProfile("sRGB"),
                        outputMode="RGB",
                    )
                except (OSError, ValueError) as exc:
                    raise MetaPublishError(
                        "Image color profile could not be normalized.", 422
                    ) from exc
            else:
                colors = color_source.convert("RGB")
            rgb = Image.new("RGB", rgba.size, "white")
            rgb.paste(colors, mask=rgba.getchannel("A"))
            if rgb.width > 1440 or rgb.height > 1800:
                rgb.thumbnail((1440, 1800), Image.Resampling.LANCZOS)
            width, height = rgb.size
            if width / height < 0.8:
                width = (height * 4 + 4) // 5
            elif width / height > 1.91:
                height = (width * 100 + 190) // 191
            if (width, height) != rgb.size:
                canvas = Image.new("RGB", (width, height), "white")
                canvas.paste(rgb, ((width - rgb.width) // 2, (height - rgb.height) // 2))
                rgb = canvas
            if rgb.width < 320:
                scale = 320 / rgb.width
                rgb = rgb.resize((320, round(rgb.height * scale)), Image.Resampling.LANCZOS)
            temporary = destination.with_suffix(".tmp")
            for quality in (85, 80, 75, 70):
                if rgb.width / rgb.height < 0.8:
                    canvas = Image.new("RGB", ((rgb.height * 4 + 4) // 5, rgb.height), "white")
                    canvas.paste(rgb, ((canvas.width - rgb.width) // 2, 0))
                    rgb = canvas
                elif rgb.width / rgb.height > 1.91:
                    canvas = Image.new("RGB", (rgb.width, (rgb.width * 100 + 190) // 191), "white")
                    canvas.paste(rgb, (0, (canvas.height - rgb.height) // 2))
                    rgb = canvas
                rgb.save(
                    temporary, format="JPEG", quality=quality, optimize=True, progressive=False
                )
                if temporary.stat().st_size < 8 * 1024 * 1024:
                    temporary.replace(destination)
                    return destination
                if rgb.width > 320:
                    next_width = max(320, round(rgb.width * 0.85))
                    rgb = rgb.resize(
                        (next_width, round(rgb.height * next_width / rgb.width)),
                        Image.Resampling.LANCZOS,
                    )
            temporary.unlink(missing_ok=True)
            raise MetaPublishError("Instagram JPEG exceeds the 8 MB limit.", 422)
    except OSError as exc:
        raise MetaPublishError("Image asset could not be served.", 422) from exc
