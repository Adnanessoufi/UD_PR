"""Explicit article import and RSS collection."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services import news_service as service
from app.services.openai_service import AIServiceError

router = APIRouter(prefix="/api/news", tags=["news"])


class ArticleRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class FeedRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=5)


@router.get("/inbox")
def inbox():
    return service.inbox()


@router.post("/feeds")
async def feeds(request: FeedRequest):
    try:
        return await service.refresh_feeds(request.urls)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/import")
async def article(request: ArticleRequest):
    try:
        return await service.import_article(request.url)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
