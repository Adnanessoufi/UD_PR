"""Server-side TikTok OAuth state and token storage for the local demo."""

import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

AUTH_DIR = Path(__file__).resolve().parents[2] / "storage" / "auth"
STATE_FILE = AUTH_DIR / "tiktok_oauth_state.json"
TOKEN_FILE = AUTH_DIR / "tiktok.json"
TOKEN_ENDPOINT = "https://open.tiktokapis.com/v2/oauth/token/"
REQUIRED_SCOPE = "video.publish"
REQUESTED_SCOPES = "user.info.basic,video.publish"
STATE_LIFETIME = timedelta(minutes=10)
STATE_LOCK = threading.Lock()


class TikTokOAuthError(Exception):
    pass


def configuration() -> tuple[str, str, str]:
    client_key = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", "").strip()
    parsed = urlparse(redirect_uri)
    if (
        not client_key
        or not client_secret
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path != "/api/tiktok/oauth/callback"
    ):
        raise TikTokOAuthError("TikTok OAuth is not configured.")
    return client_key, client_secret, redirect_uri


def _save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


def create_state() -> str:
    state = secrets.token_urlsafe(32)
    with STATE_LOCK:
        _save_json(
            STATE_FILE,
            {
                "state": state,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    return state


def consume_state(returned_state: str) -> bool:
    with STATE_LOCK:
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            expected = saved["state"]
            created_at = datetime.fromisoformat(saved["created_at"])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return False

        now = datetime.now(timezone.utc)
        if (
            not isinstance(expected, str)
            or not expected
            or now - created_at > STATE_LIFETIME
            or created_at > now
        ):
            try:
                STATE_FILE.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        if not returned_state or not hmac.compare_digest(expected, returned_state):
            return False
        try:
            STATE_FILE.unlink(missing_ok=True)
        except OSError:
            return False
        return True


def _scope_set(raw_scope: str) -> set[str]:
    return {scope.strip() for scope in raw_scope.split(",") if scope.strip()}


def has_publish_scope(raw_scope: str) -> bool:
    return REQUIRED_SCOPE in _scope_set(raw_scope)


def _normalize_tokens(payload: dict, previous: dict | None = None) -> dict:
    try:
        scope = payload["scope"]
        access_token = payload["access_token"]
        refresh_token = payload.get("refresh_token") or (previous or {}).get("refresh_token")
        open_id = payload.get("open_id") or (previous or {}).get("open_id")
        token_type = payload["token_type"]
        expires_in = int(payload["expires_in"])
        refresh_expires_in = int(payload["refresh_expires_in"])
        if (
            not isinstance(scope, str)
            or not has_publish_scope(scope)
            or not isinstance(access_token, str)
            or not access_token
            or not isinstance(refresh_token, str)
            or not refresh_token
            or not isinstance(open_id, str)
            or not open_id
            or not isinstance(token_type, str)
            or token_type.lower() != "bearer"
            or expires_in <= 0
            or refresh_expires_in <= 0
        ):
            raise ValueError("Invalid TikTok token response")
        now = datetime.now(timezone.utc)
        return {
            "access_token": access_token,
            "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
            "refresh_token": refresh_token,
            "refresh_expires_at": (now + timedelta(seconds=refresh_expires_in)).isoformat(),
            "open_id": open_id,
            "scope": scope,
            "token_type": token_type,
        }
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise TikTokOAuthError("TikTok did not return a usable authorization.") from exc


async def _request_tokens(data: dict[str, str]) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(TOKEN_ENDPOINT, data=data)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("error"):
            raise TikTokOAuthError("TikTok authorization failed.")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise TikTokOAuthError("TikTok authorization failed.") from exc


async def exchange_code(code: str) -> None:
    client_key, client_secret, redirect_uri = configuration()
    payload = await _request_tokens(
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    )
    saved = _normalize_tokens(payload)
    try:
        _save_json(TOKEN_FILE, saved)
    except OSError as exc:
        raise TikTokOAuthError("TikTok credentials could not be saved.") from exc


async def refresh_access_token() -> str:
    """Refresh internally when a future TikTok API operation needs a new token."""
    try:
        saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        refresh_token = saved["refresh_token"]
        refresh_expiry = datetime.fromisoformat(saved["refresh_expires_at"])
        if refresh_expiry.tzinfo is None:
            refresh_expiry = refresh_expiry.replace(tzinfo=timezone.utc)
        if not refresh_token or refresh_expiry <= datetime.now(timezone.utc):
            raise TikTokOAuthError("TikTok must be reconnected.")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise TikTokOAuthError("TikTok must be reconnected.") from exc

    client_key, client_secret, _ = configuration()
    payload = await _request_tokens(
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    )
    refreshed = _normalize_tokens(payload, previous=saved)
    try:
        _save_json(TOKEN_FILE, refreshed)
    except OSError as exc:
        raise TikTokOAuthError("TikTok credentials could not be saved.") from exc
    return refreshed["access_token"]


def connection_status() -> dict:
    try:
        saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        scope = saved["scope"]
        refresh_expiry = datetime.fromisoformat(saved["refresh_expires_at"])
        if refresh_expiry.tzinfo is None:
            refresh_expiry = refresh_expiry.replace(tzinfo=timezone.utc)
        if (
            saved.get("access_token")
            and saved.get("refresh_token")
            and refresh_expiry > datetime.now(timezone.utc)
            and isinstance(scope, str)
            and has_publish_scope(scope)
        ):
            return {"connected": True, "scope": scope}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return {"connected": False}
