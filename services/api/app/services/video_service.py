import hashlib
import os
import uuid
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.video import Video
from app.models.job import AnalysisJob, JobStatus

settings = get_settings()


async def compute_file_hash(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


async def save_upload(file: UploadFile) -> tuple[str, str, int]:
    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.upload_dir, filename)

    file_size = 0
    with open(filepath, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            if file_size > settings.max_upload_size_mb * 1024 * 1024:
                os.remove(filepath)
                raise ValueError(f"File exceeds {settings.max_upload_size_mb}MB limit")
            f.write(chunk)

    return filename, filepath, file_size


async def create_video_and_job(
    db: AsyncSession,
    filename: str,
    original_name: str,
    file_size: int,
    mime_type: str,
    file_path: str,
    file_hash: str,
) -> tuple[Video, AnalysisJob]:
    video = Video(
        filename=filename,
        original_name=original_name,
        file_size=file_size,
        mime_type=mime_type,
        file_hash=file_hash,
        storage_path=file_path,
    )
    db.add(video)
    await db.flush()

    job = AnalysisJob(video_id=video.id, status=JobStatus.PENDING.value)
    db.add(job)
    await db.commit()
    await db.refresh(video)
    await db.refresh(job)
    return video, job


async def get_video(db: AsyncSession, video_id: uuid.UUID) -> Video | None:
    result = await db.execute(select(Video).where(Video.id == video_id))
    return result.scalar_one_or_none()


async def list_videos(
    db: AsyncSession, page: int = 1, per_page: int = 20, search: str | None = None
) -> tuple[list[Video], int]:
    query = select(Video).order_by(Video.created_at.desc())
    count_query = select(func.count(Video.id))

    if search:
        query = query.where(Video.original_name.ilike(f"%{search}%"))
        count_query = count_query.where(Video.original_name.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.offset((page - 1) * per_page).limit(per_page))
    return list(result.scalars().all()), total
