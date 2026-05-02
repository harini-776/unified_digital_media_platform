from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.video import Video
from app.schemas.video import VideoUploadResponse, VideoResponse, VideoListResponse
from app.services.video_service import save_upload, compute_file_hash, create_video_and_job, list_videos
from app.tasks.analyze import run_video_analysis

router = APIRouter()

ALLOWED_TYPES = {"video/mp4", "video/avi", "video/x-msvideo", "video/quicktime", "video/x-matroska", "video/webm"}


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a video file for deepfake analysis.

    Returns a job_id to track analysis progress.
    """
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}. Allowed: {ALLOWED_TYPES}")

    try:
        filename, filepath, file_size = await save_upload(file)
    except ValueError as e:
        raise HTTPException(413, str(e))

    file_hash = await compute_file_hash(filepath)

    video, job = await create_video_and_job(
        db=db,
        filename=filename,
        original_name=file.filename or "unknown.mp4",
        file_size=file_size,
        mime_type=file.content_type,
        file_path=filepath,
        file_hash=file_hash,
    )

    # Dispatch async analysis task
    run_video_analysis.delay(str(job.id), str(video.id))

    return VideoUploadResponse(video_id=video.id, job_id=job.id)


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Serve the uploaded video file for inline playback."""
    import os
    from sqlalchemy import select
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(404, "Video not found")
    if not os.path.exists(video.storage_path):
        raise HTTPException(404, "Video file not found on disk")
    return FileResponse(
        video.storage_path,
        media_type=video.mime_type or "video/mp4",
        filename=video.original_name,
    )


@router.get("", response_model=VideoListResponse)
async def get_videos(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded videos with pagination."""
    videos, total = await list_videos(db, page=page, per_page=per_page, search=search)
    return VideoListResponse(
        videos=[VideoResponse.model_validate(v) for v in videos],
        total=total,
        page=page,
        per_page=per_page,
    )
