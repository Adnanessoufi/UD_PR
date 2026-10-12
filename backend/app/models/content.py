from typing import Literal

from pydantic import BaseModel


class SourceFact(BaseModel):
    id: str
    statement: str
    category: str
    page: int | None
    source_excerpt: str
    importance: Literal["high", "medium", "low"]


class ResearchSource(BaseModel):
    title: str
    url: str
    domain: str
    source_type: Literal["official", "secondary"]


class SourceAnalysis(BaseModel):
    document_type: str
    source_language: str
    title: str
    organization: str
    people: list[str]
    summary: str
    key_facts: list[SourceFact]
    important_numbers: list[str]
    important_dates: list[str]
    conditions_and_limitations: list[str]
    communication_focus: str
    source_links: list[str] = []
    research_sources: list[ResearchSource] = []
    warning: str | None = None


class ConsolidatedOverview(BaseModel):
    document_type: str
    source_language: str
    title: str
    organization: str
    people: list[str]
    summary: str
    selected_fact_ids: list[str]
    important_numbers: list[str]
    important_dates: list[str]
    conditions_and_limitations: list[str]
    communication_focus: str


class MasterContent(BaseModel):
    headline: str
    lead: str
    body: str
    short_summary: str
    key_messages: list[str]
    press_release: str
    source_fact_ids: list[str]


class CombinedResult(BaseModel):
    analysis: SourceAnalysis
    content: MasterContent
    output_language: Literal["en", "hu"] = "en"
