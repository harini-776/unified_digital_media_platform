from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.job import AnalysisJob
from app.models.user import User, UserRole
from app.schemas.job import JobStatusResponse

router = APIRouter()


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the status and progress of an analysis job. Owner-only (admins see all)."""
    result = await db.execute(
        select(AnalysisJob)
        .options(selectinload(AnalysisJob.video))
        .where(AnalysisJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(404, "Job not found")

    if user.role != UserRole.ADMIN.value and job.video.user_id != user.id:
        # 404, not 403 — see assert_video_owner: don't leak existence via response code.
        raise HTTPException(404, "Job not found")

    return JobStatusResponse.model_validate(job)
