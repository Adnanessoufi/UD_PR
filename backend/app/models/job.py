from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

JobState = Literal["queued", "running", "ready", "failed", "cancelled", "interrupted"]


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(min_length=2, max_length=61)
    arguments: dict = Field(default_factory=dict)


class JobRecord(BaseModel):
    id: UUID
    run_id: UUID
    task_id: str
    label: str
    arguments: dict
    state: JobState = "queued"
    progress: int = 0
    message: str = "Queued"
    created_at: datetime
    updated_at: datetime
    attempt: int = 1
    retry_of: UUID | None = None
    result: dict | None = None
    error: str | None = None
