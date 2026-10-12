"""TikTok Login Kit connection and Direct Post routes."""

import asyncio
import os
import re
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from app.services.openai_service import AIServiceError
from app.services.verification_service import require_approval
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.services.tiktok_oauth_service import (
    REQUESTED_SCOPES,
    TikTokOAuthError,
    configuration,
    connection_status,
    consume_state,
    create_state,
    exchange_code,
    has_publish_scope,
)
from app.services.tiktok_publish_service import (
    TikTokPublishError,
    check_publish_status,
    local_status,
    publish_video,
)


router = APIRouter(prefix="/api/tiktok", tags=["tiktok"])
FRONTEND_URL = "http://localhost:5173/"
PUBLISH_LOCKS: dict[UUID, asyncio.Lock] = {}


def _frontend_redirect(connected: bool) -> RedirectResponse:
    result = "connected" if connected else "error"
    response = RedirectResponse(f"{FRONTEND_URL}?tiktok={result}", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/oauth/start")
def start_oauth():
    try:
        client_key, _, redirect_uri = configuration()
        state = create_state()
    except (TikTokOAuthError, OSError):
        return _frontend_redirect(False)
    query = urlencode(
        {
            "client_key": client_key,
            "response_type": "code",
            "scope": REQUESTED_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    response = RedirectResponse(
        f"https://www.tiktok.com/v2/auth/authorize/?{query}", status_code=302
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/oauth/callback")
async def oauth_callback(request: Request):
    params = request.query_params
    if not consume_state(params.get("state", "")):
        return _frontend_redirect(False)
    if params.get("error") or params.get("error_description") or not params.get("code"):
        return _frontend_redirect(False)
    granted_scopes = params.get("scopes")
    if granted_scopes is not None and not has_publish_scope(granted_scopes):
        return _frontend_redirect(False)
    try:
        await exchange_code(params["code"])
    except TikTokOAuthError:
        return _frontend_redirect(False)
    return _frontend_redirect(True)


@router.get("/status")
def status():
    result = connection_status()
    parsed = urlsplit(os.getenv("TIKTOK_PROFILE_URL", "").strip())
    if (
        parsed.scheme == "https"
        and parsed.netloc in {"tiktok.com", "www.tiktok.com"}
        and re.fullmatch(r"/@[A-Za-z0-9._]+/?", parsed.path)
        and not parsed.query
        and not parsed.fragment
    ):
        result["profile_url"] = f"https://www.tiktok.com{parsed.path.rstrip('/')}"
    return result


@router.get("/publish/{run_id}")
def publication_status(run_id: UUID):
    try:
        return local_status(run_id)
    except TikTokPublishError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/publish/{run_id}")
async def publish_tiktok(run_id: UUID):
    lock = PUBLISH_LOCKS.setdefault(run_id, asyncio.Lock())
    async with lock:
        try:
            require_approval(
                Path(__file__).resolve().parents[2] / "storage" / str(run_id), "tiktok"
            )
            return await publish_video(run_id)
        except AIServiceError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
        except TikTokPublishError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/publish/{run_id}/status")
async def check_tiktok_publish_status(run_id: UUID):
    lock = PUBLISH_LOCKS.setdefault(run_id, asyncio.Lock())
    async with lock:
        try:
            return await check_publish_status(run_id)
        except TikTokPublishError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
