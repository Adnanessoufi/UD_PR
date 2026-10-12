"""Claim review, page evidence and human approval endpoints."""

from pathlib import Path
from uuid import UUID
import pymupdf
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError
from app.models.verification import ApprovalRequest, ReviewContext, ReviewStatus, VerificationReport
from app.services.openai_service import AIServiceError
from app.services.verification_service import approve, review_status, verify

router = APIRouter(prefix="/api/verification", tags=["verification"])
STORAGE = Path(__file__).resolve().parents[2] / "storage"


class CheckRequest(ReviewContext):
    force: bool = False


class HumanReviewRequest(BaseModel):
    context: ReviewContext
    approval: ApprovalRequest


def folder(run_id: UUID) -> Path:
    path = STORAGE / str(run_id)
    if not path.is_dir():
        raise HTTPException(404, "Document run was not found.")
    return path


@router.post("/{run_id}/status", response_model=ReviewStatus)
def status(run_id: UUID, context: ReviewContext):
    try:
        return review_status(folder(run_id), context)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except (ValidationError, KeyError, TypeError) as exc:
        raise HTTPException(
            422, "Saved content is incomplete. Generate the package again."
        ) from exc


@router.post("/{run_id}/check", response_model=ReviewStatus)
async def check(run_id: UUID, request: CheckRequest):
    try:
        return await verify(
            folder(run_id),
            ReviewContext(**request.model_dump(exclude={"force"})),
            force=request.force,
        )
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except (ValidationError, KeyError, TypeError) as exc:
        raise HTTPException(422, "Saved content or checker response is invalid.") from exc


@router.post("/{run_id}/approve", response_model=ReviewStatus)
def human_approval(run_id: UUID, request: HumanReviewRequest):
    try:
        return approve(folder(run_id), request.context, request.approval)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except (ValidationError, KeyError, TypeError) as exc:
        raise HTTPException(422, "Review data is invalid.") from exc


@router.get("/{run_id}/evidence/{claim_id}/{evidence_index}")
def evidence_page(run_id: UUID, claim_id: str, evidence_index: int):
    run = folder(run_id)
    try:
        report = VerificationReport.model_validate_json(
            (run / "verification.json").read_text(encoding="utf-8")
        )
        current = review_status(run, report.context)
        if current.report is None:
            raise HTTPException(409, "Verification is stale. Check the current package again.")
        claim = next((item for item in report.claims if item.id == claim_id), None)
        if claim is None or not 0 <= evidence_index < len(claim.evidence):
            raise HTTPException(404, "Evidence was not found.")
        evidence = claim.evidence[evidence_index]
        if (
            evidence.source_type != "document"
            or evidence.page is None
            or not (run / "source.pdf").is_file()
        ):
            raise HTTPException(
                404, "This evidence has no PDF page. Read the source excerpt instead."
            )
        with pymupdf.open(run / "source.pdf") as document:
            if not 1 <= evidence.page <= len(document):
                raise HTTPException(404, "Source page was not found.")
            page = document[evidence.page - 1]
            rectangles = page.search_for(" ".join(evidence.excerpt.split()), quads=True)
            if rectangles:
                annotation = page.add_highlight_annot(rectangles)
                annotation.update()
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3), alpha=False)
            return Response(
                pixmap.tobytes("png"),
                media_type="image/png",
                headers={
                    "Cache-Control": "no-store",
                    "X-Evidence-Highlighted": str(bool(rectangles)).lower(),
                },
            )
    except HTTPException:
        raise
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except (OSError, ValueError, ValidationError, pymupdf.FileDataError) as exc:
        raise HTTPException(422, "The source page could not be rendered.") from exc
