"""Audience preview history and the original cited PDF page."""

from uuid import UUID
import pymupdf
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.api.verification import folder
from app.models.story_room import StoryAnswer
from app.services.story_room_service import history
from app.services.openai_service import AIServiceError

router = APIRouter(prefix="/api/story-room", tags=["story room"])


@router.get("/{run_id}/answers", response_model=list[StoryAnswer])
def answers(run_id: UUID):
    try:
        return history(folder(run_id))
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.get("/{run_id}/answers/{answer_id}/evidence/{index}")
def evidence_page(run_id: UUID, answer_id: str, index: int):
    run = folder(run_id)
    try:
        answer = next((item for item in history(run) if item.id == answer_id), None)
        if answer is None or not 0 <= index < len(answer.evidence):
            raise HTTPException(404, "Answer evidence was not found.")
        evidence = answer.evidence[index]
        if evidence.page is None or not (run / "source.pdf").is_file():
            raise HTTPException(404, "This source has no PDF page. Read the excerpt instead.")
        with pymupdf.open(run / "source.pdf") as doc:
            if not 1 <= evidence.page <= len(doc):
                raise HTTPException(404, "Source page was not found.")
            page = doc[evidence.page - 1]
            rects = page.search_for(" ".join(evidence.excerpt.split()), quads=True)
            if rects:
                page.add_highlight_annot(rects).update()
            return Response(
                page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3), alpha=False).tobytes("png"),
                media_type="image/png",
                headers={
                    "Cache-Control": "no-store",
                    "X-Evidence-Highlighted": str(bool(rects)).lower(),
                },
            )
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
