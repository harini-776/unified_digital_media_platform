from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class JobStatusResponse(BaseModel):
    id: UUID
    video_id: UUID
    status: str
    progress: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
