from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import get_settings
from app.models.job import AnalysisJob
from app.models.result import AnalysisResult
from app.models.video import Video
from app.models.blockchain import BlockchainRecord
from app.schemas.result import AnalysisResultResponse, SignalBreakdown, BlockchainStatus

settings = get_settings()
router = APIRouter()


@router.get("/{video_id}/result", response_model=AnalysisResultResponse)
async def get_video_result(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the analysis result for a specific video."""
    # Find the latest completed job for this video
    job_result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.video_id == video_id, AnalysisJob.status == "completed")
        .order_by(AnalysisJob.completed_at.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(404, "No completed analysis found for this video")

    result_query = await db.execute(
        select(AnalysisResult).where(AnalysisResult.job_id == job.id)
    )
    result = result_query.scalar_one_or_none()

    if not result:
        raise HTTPException(404, "Analysis result not found")

    video_query = await db.execute(select(Video).where(Video.id == video_id))
    video = video_query.scalar_one_or_none()

    # Check for blockchain record
    bc_record = None
    if video:
        bc_query = await db.execute(
            select(BlockchainRecord).where(BlockchainRecord.video_hash == video.file_hash)
        )
        bc_record = bc_query.scalar_one_or_none()

    return AnalysisResultResponse(
        id=result.id,
        job_id=result.job_id,
        video_id=video_id,
        fake_probability=result.fake_probability,
        trust_score=result.trust_score,
        verdict=result.verdict,
        confidence=result.confidence,
        # New calibrated + uncertainty fields
        confidence_calibrated_probability=result.confidence_calibrated_probability,
        uncertainty_flag=result.uncertainty_flag,
        entropy=result.entropy,
        explanation=result.explanation,
        modality_weights=result.modality_weights,
        fusion_method=result.fusion_method,
        signals=SignalBreakdown(
            face_score=result.face_score,
            lipsync_score=result.lipsync_score,
            voice_score=result.voice_score,
            blink_score=result.blink_score,
            headmotion_score=result.headmotion_score,
            details=result.signal_details,
        ),
        blockchain=BlockchainStatus(
            verified=result.blockchain_verified,
            match=result.blockchain_match,
            tx_hash=bc_record.tx_hash if bc_record else None,
            ipfs_cid=bc_record.ipfs_cid if bc_record else None,
            network=bc_record.network if bc_record else None,
        ),
        created_at=result.created_at,
        video_name=video.original_name if video else None,
        share_url=f"/share/{result.id}",
    )
