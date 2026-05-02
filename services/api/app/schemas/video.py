from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class VideoUploadResponse(BaseModel):
    video_id: UUID
    job_id: UUID
    message: str = "Upload successful. Analysis started."


class VideoResponse(BaseModel):
    id: UUID
    filename: str
    original_name: str
    file_size: int
    mime_type: str
    duration_seconds: float | None
    file_hash: str
    ipfs_cid: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class VideoListResponse(BaseModel):
    videos: list[VideoResponse]
    total: int
    page: int
    per_page: int
