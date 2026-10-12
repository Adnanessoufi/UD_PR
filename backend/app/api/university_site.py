"""Local demo University news publication and retrieval."""

from uuid import UUID

from app.services.openai_service import AIServiceError
from app.services.verification_service import require_approval
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.university_site_service import (
    UniversitySiteError,
    article_for_run,
    list_articles,
    load_article,
    publish_article,
)


router = APIRouter(prefix="/api/university-site", tags=["university-site"])


class PublishRequest(BaseModel):
    primary_media_id: str | None = None
    media_ids: list[str] = Field(default_factory=list)


@router.post("/publish/{run_id}")
def publish(run_id: UUID, request: PublishRequest) -> dict:
    try:
        require_approval(
            Path(__file__).resolve().parents[2] / "storage" / str(run_id),
            "website",
            primary_media_id=request.primary_media_id,
            media_ids=request.media_ids,
        )
        return publish_article(run_id, request.primary_media_id, request.media_ids)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except UniversitySiteError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.get("/status/{run_id}")
def status(run_id: UUID) -> dict:
    try:
        return {"published": article_for_run(run_id)}
    except UniversitySiteError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.get("/articles")
def articles() -> list[dict]:
    return list_articles()


@router.get("/articles/{slug}")
def article(slug: str) -> dict:
    try:
        return load_article(slug)
    except UniversitySiteError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
