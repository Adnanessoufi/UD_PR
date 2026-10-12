"""Campaign preferences and persistent workspace state."""

from typing import Literal
from pydantic import BaseModel, Field
from app.models.platform import PlatformRequest


class CampaignBrief(BaseModel):
    audience: Literal["general_public", "students", "industry", "researchers"] = "general_public"
    tone: Literal["institutional", "friendly", "energetic"] = "institutional"
    length: Literal["short", "standard", "detailed"] = "standard"
    focus: str = Field(default="", max_length=300)
    call_to_action: str = Field(default="", max_length=200)


class CampaignMetadata(BaseModel):
    name: str = Field(default="", max_length=140)
    archived: bool = False
    starred: bool = False


class WorkspaceState(PlatformRequest):
    pass
