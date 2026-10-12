"""Evidence, independent checking, and version-specific human approval."""

from typing import Literal
from pydantic import BaseModel, Field
from app.models.platform import PlatformName

Verdict = Literal["supported", "exaggerated", "unsupported", "needs_review", "non_factual"]


class ReviewContext(BaseModel):
    platforms: list[PlatformName] = Field(min_length=1)
    primary_media_id: str | None = None
    media_ids: list[str] = Field(default_factory=list)


class EvidenceReference(BaseModel):
    passage_id: str
    excerpt: str


class CheckedUnit(BaseModel):
    id: str
    verdict: Verdict
    explanation: str
    suggested_revision: str
    evidence: list[EvidenceReference]


class CheckerResult(BaseModel):
    items: list[CheckedUnit]


class Evidence(BaseModel):
    passage_id: str
    source_type: Literal["document", "web", "user"]
    page: int | None
    excerpt: str
    url: str | None = None


class NumberCheck(BaseModel):
    token: str
    status: Literal["matched", "missing_source", "missing_evidence"]


class ClaimReview(BaseModel):
    id: str
    channel: str
    field: str
    text: str
    verdict: Verdict
    explanation: str
    suggested_revision: str
    evidence: list[Evidence]
    number_checks: list[NumberCheck]


class VerificationReport(BaseModel):
    version: str
    checked_at: str
    writer_model: str
    checker_model: str
    context: ReviewContext
    claims: list[ClaimReview]


class ApprovalRequest(BaseModel):
    version: str
    reviewer: str = Field(min_length=2, max_length=100)
    reviewed_claims: bool
    reviewed_media: bool


class Approval(BaseModel):
    version: str
    reviewer: str
    approved_at: str
    reviewed_claims: bool
    reviewed_media: bool


class ReviewStatus(BaseModel):
    version: str
    report: VerificationReport | None
    approval: Approval | None
    state: Literal["unchecked", "needs_review", "verified", "approved"]
    blocking_count: int
    checker_ready: bool
    configuration_message: str | None
