"""Local YouTube OAuth connection for the demo account."""

import asyncio
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

import httpx
import logging
from dotenv import load_dotenv
from app.services.openai_service import AIServiceError
from app.services.verification_service import require_approval

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.services.youtube_publish_service import (
    YouTubePublishError,
    load_publication,
    publish_video,
)


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

router = APIRouter(prefix="/api/youtube", tags=["youtube"])
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT_URI = "http://localhost:8001/api/youtube/oauth/callback"
FRONTEND_URL = "http://localhost:5173/"
STATE_COOKIE = "youtube_oauth_state"
TOKEN_FILE = Path(__file__).resolve().parents[2] / "storage" / "auth" / "youtube.json"
PUBLISH_LOCKS: dict[UUID, asyncio.Lock] = {}
LOGGER = logging.getLogger("uvicorn.error")


class PublishRequest(BaseModel):
    title: str | None = None
    description: str | None = None


def _frontend_redirect(connected: bool) -> RedirectResponse:
    result = "connected" if connected else "error"
    response = RedirectResponse(f"{FRONTEND_URL}?youtube={result}", status_code=303)
    response.delete_cookie(STATE_COOKIE, path="/api/youtube/oauth")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/oauth/start")
def start_oauth():
    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    configured_redirect = os.getenv("YOUTUBE_REDIRECT_URI", "").strip()
    if not client_id or not client_secret or configured_redirect != REDIRECT_URI:
        return _frontend_redirect(False)

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    response = RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}",
        status_code=302,
    )
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        path="/api/youtube/oauth",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    expected_state = request.cookies.get(STATE_COOKIE, "")
    received_state = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    if (
        not expected_state
        or not received_state
        or not hmac.compare_digest(expected_state, received_state)
    ):
        return _frontend_redirect(False)
    if request.query_params.get("error") or not code:
        return _frontend_redirect(False)

    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    if (
        not client_id
        or not client_secret
        or os.getenv("YOUTUBE_REDIRECT_URI", "").strip() != REDIRECT_URI
    ):
        return _frontend_redirect(False)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            result = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            result.raise_for_status()
            token = result.json()

        granted_scope = token.get("scope", "")
        expires_in = int(token.get("expires_in", 0))
        if (
            SCOPE not in granted_scope.split()
            or not token.get("access_token")
            or not token.get("refresh_token")
            or not token.get("token_type")
            or expires_in <= 0
        ):
            return _frontend_redirect(False)

        saved = {
            "access_token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
            "scope": granted_scope,
            "token_type": token["token_type"],
        }
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = TOKEN_FILE.with_suffix(".json.tmp")
        temporary_file.write_text(json.dumps(saved), encoding="utf-8")
        temporary_file.replace(TOKEN_FILE)
    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        AttributeError,
        OSError,
        KeyError,
        OverflowError,
    ):
        return _frontend_redirect(False)

    return _frontend_redirect(True)


@router.get("/status")
def youtube_status():
    try:
        saved = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        if saved.get("refresh_token") and SCOPE in saved.get("scope", "").split():
            return {"connected": True, "scope": SCOPE}
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return {"connected": False}


@router.get("/publish/{run_id}/status")
def publication_status(run_id: UUID):
    run_dir = TOKEN_FILE.parent.parent / str(run_id)
    if not run_dir.is_dir():
        raise HTTPException(404, "Document run was not found.")
    return load_publication(run_dir) or {"success": False}


@router.post("/publish/{run_id}")
async def publish_youtube(run_id: UUID, details: PublishRequest | None = None):
    lock = PUBLISH_LOCKS.setdefault(run_id, asyncio.Lock())
    async with lock:
        try:
            require_approval(TOKEN_FILE.parent.parent / str(run_id), "youtube")
            return await asyncio.to_thread(
                publish_video,
                run_id,
                None,  # Publish only saved, verified metadata; request fallbacks cannot bypass approval.
                None,
            )
        except AIServiceError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        except YouTubePublishError as exc:
            if exc.diagnostics:
                return JSONResponse(
                    status_code=exc.status_code, content={"detail": str(exc), **exc.diagnostics}
                )
            LOGGER.error(
                "[YouTube] publish failed: exception=%s message=%s", type(exc).__name__, str(exc)
            )
            raise HTTPException(exc.status_code, str(exc)) from exc
