import os
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.database import get_db
from app.core.deps import assert_video_owner, get_current_user
from app.core.limiter import limiter
from app.core.security import (
    StreamTokenError,
    make_stream_token,
    verify_stream_token,
)
from app.models.user import User, UserRole
from app.models.video import Video
from app.schemas.video import VideoUploadResponse, VideoResponse, VideoListResponse
from app.services.video_service import (
    save_upload,
    compute_file_hash,
    create_video_and_job,
    list_videos,
)
from app.tasks.analyze import run_video_analysis

router = APIRouter()

ALLOWED_TYPES = {
    "video/mp4",
    "video/avi",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
}


@router.post("/upload", response_model=VideoUploadResponse)
@limiter.limit("10/hour")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a video file for deepfake analysis.

    Returns a job_id to track analysis progress. Authenticated; the uploaded
    video is owned by the calling user.
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
        user_id=user.id,
    )

    run_video_analysis.delay(str(job.id), str(video.id))

    audit(
        "video.upload",
        user_id=user.id,
        target_type="video",
        target_id=video.id,
        job_id=str(job.id),
        size=file_size,
    )

    return VideoUploadResponse(video_id=video.id, job_id=job.id)


@router.get("/{video_id}/stream-url")
async def get_stream_url(
    request: Request,
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mint a short-lived signed URL the client can hand to a <video> tag.

    <video> elements cannot send Authorization headers, so the streaming
    endpoint validates a query-string HMAC token instead. The token expires
    in 5 minutes and is bound to (video_id, user_id).
    """
    video = await assert_video_owner(db, video_id, user)
    token = make_stream_token(video.id, user.id)
    audit("video.stream_url.mint", user_id=user.id, target_type="video", target_id=video.id)
    return {
        "url": f"/api/v1/videos/{video.id}/stream?token={token}",
        "expires_in": 300,
    }


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Serve the video file. Validates the HMAC token from /stream-url.

    No Bearer auth — see /stream-url for the rationale.
    """
    try:
        user_id = verify_stream_token(token, video_id)
    except StreamTokenError:
        raise HTTPException(403, "Invalid or expired stream token")

    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if video is None:
        raise HTTPException(404, "Video not found")

    if video.user_id != user_id:
        # Token's embedded user_id doesn't match this video's owner.
        # The HMAC was valid (so the token wasn't forged), but the user it was
        # minted for is not the owner — this can only happen if the video's
        # ownership changed after the token was minted, or the token was
        # minted via an admin path. Reject either way.
        raise HTTPException(403, "Stream token user mismatch")

    if not os.path.exists(video.storage_path):
        raise HTTPException(404, "Video file not found on disk")

    audit("video.stream", user_id=user_id, target_type="video", target_id=video.id)
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
    user: User = Depends(get_current_user),
):
    """List the calling user's videos. Admins see all videos."""
    owner_filter = None if user.role == UserRole.ADMIN.value else user.id
    videos, total = await list_videos(
        db, page=page, per_page=per_page, search=search, owner_id=owner_filter
    )
    return VideoListResponse(
        videos=[VideoResponse.model_validate(v) for v in videos],
        total=total,
        page=page,
        per_page=per_page,
    )
