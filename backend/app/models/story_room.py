"""Source-grounded audience questions; drafts never publish themselves."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StoryQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=5, max_length=600)
    language: Literal["en", "hu"] = "en"


class AnswerCitation(BaseModel):
    passage_id: str
    excerpt: str = Field(min_length=6, max_length=300)


class GroundedAnswer(BaseModel):
    status: Literal["answered", "not_in_source"]
    answer: str
    short_reply: str
    caveat: str
    evidence: list[AnswerCitation]


class StoryEvidence(BaseModel):
    excerpt: str
    page: int | None
    url: str | None
    source_type: str


class StoryAnswer(BaseModel):
    id: str
    question: str
    language: Literal["en", "hu"]
    status: Literal["answered", "not_in_source"]
    answer: str
    short_reply: str
    caveat: str
    evidence: list[StoryEvidence]
    source_fingerprint: str
    generated_at: str
    excerpts_confirmed: bool
