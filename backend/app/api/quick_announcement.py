"""Create a communication run from one short announcement."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.content import CombinedResult
from app.services.output_language import OutputLanguage
from app.services.openai_service import AIServiceError
from app.services.quick_announcement_service import create_quick_announcement, quick_status


router = APIRouter(prefix="/api", tags=["quick announcement"])


from app.models.campaign import CampaignBrief


class QuickRequest(BaseModel):
    brief: CampaignBrief | None = None
    text: str = Field(min_length=8, max_length=500)
    run_id: UUID | None = None
    include_images: bool = True
    language: OutputLanguage = "en"


class QuickResponse(BaseModel):
    run_id: str
    combined: CombinedResult


@router.post("/quick-announcements", response_model=QuickResponse)
async def create(request: QuickRequest) -> QuickResponse:
    if len(request.text.strip()) < 8:
        raise HTTPException(422, "Write a short announcement first.")
    try:
        run_id, combined = await create_quick_announcement(
            request.text, request.run_id, request.include_images, request.language, request.brief
        )
        return QuickResponse(run_id=run_id, combined=combined)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.get("/quick-announcements/{run_id}/status")
def status(run_id: UUID) -> dict[str, str]:
    return quick_status(run_id)
