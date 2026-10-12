from typing import Literal

from pydantic import BaseModel

ContentType = Literal["text", "image", "video"]
OutputLanguage = Literal["en", "hu"]
PlatformName = Literal["website", "linkedin", "facebook", "instagram", "tiktok", "youtube"]


class PlatformRequest(BaseModel):
    content_types: list[ContentType]
    platforms: list[PlatformName]
    language: OutputLanguage = "en"


class PlatformPost(BaseModel):
    platform: PlatformName
    title: str
    body: str
    source_fact_ids: list[str]


class PlatformAdaptations(BaseModel):
    items: list[PlatformPost]


class PlatformResult(PlatformRequest):
    items: list[PlatformPost]
