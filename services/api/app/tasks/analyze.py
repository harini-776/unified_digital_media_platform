"""
Celery task for video analysis.
Runs the AI pipeline in background and stores results.
"""
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.models.job import AnalysisJob, JobStatus
from app.models.result import AnalysisResult
from app.models.video import Video
from app.services.ai.pipeline import run_analysis
from app.services.blockchain_service import verify_on_chain

settings = get_settings()

# Sync engine for Celery (Celery doesn't support async natively)
sync_engine = create_engine(settings.database_url)
SyncSession = sessionmaker(bind=sync_engine)


@celery_app.task(name="app.tasks.analyze.run_video_analysis", bind=True,
                 time_limit=300, soft_time_limit=270)
def run_video_analysis(self, job_id: str, video_id: str):
    """Execute the full analysis pipeline for a video."""
    db = SyncSession()
    job = None  # ensure job is always bound before except block
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == uuid.UUID(job_id)).first()
        video = db.query(Video).filter(Video.id == uuid.UUID(video_id)).first()

        if not job or not video:
            return {"error": "Job or video not found"}

        # Update job status
        job.status = JobStatus.PROCESSING.value
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        def update_progress(stage: str, percent: int):
            job.status = stage
            job.progress = percent
            db.commit()
            self.update_state(state="PROGRESS", meta={"stage": stage, "progress": percent})

        # Run AI pipeline
        update_progress("extracting", 5)
        ai_result = run_analysis(video.storage_path, progress_callback=update_progress)

        # Check blockchain provenance
        update_progress("blockchain_check", 92)
        blockchain_result = None
        blockchain_verified = None
        blockchain_match = None

        try:
            import asyncio
            loop = asyncio.new_event_loop()
            bc_check = loop.run_until_complete(verify_on_chain(video.file_hash))
            loop.close()

            if bc_check.get("found"):
                blockchain_verified = True
                blockchain_match = bc_check.get("match", False)

                # Decision engine: blockchain overrides AI if record exists
                if blockchain_match:
                    ai_result["verdict"] = "authentic"
                    ai_result["trust_score"] = 100
                    ai_result["confidence"] = 1.0
                else:
                    ai_result["verdict"] = "manipulated"
                    ai_result["trust_score"] = 0
                    ai_result["confidence"] = 1.0
        except Exception:
            pass  # Blockchain check is optional

        def _f(v):
            """Cast numpy scalars to native Python float for psycopg2 compatibility."""
            return float(v) if v is not None else None

        # Store result
        result = AnalysisResult(
            job_id=job.id,
            fake_probability=_f(ai_result["fake_probability"]),
            trust_score=_f(ai_result["trust_score"]),
            verdict=ai_result["verdict"],
            confidence=_f(ai_result["confidence"]),
            face_score=_f(ai_result.get("face_score")),
            lipsync_score=_f(ai_result.get("lipsync_score")),
            voice_score=_f(ai_result.get("voice_score")),
            blink_score=_f(ai_result.get("blink_score")),
            headmotion_score=_f(ai_result.get("headmotion_score")),
            signal_details=ai_result.get("signal_details"),
            # New calibrated + uncertainty fields
            confidence_calibrated_probability=_f(ai_result.get("confidence_calibrated_probability")),
            uncertainty_flag=ai_result.get("uncertainty_flag"),
            entropy=_f(ai_result.get("entropy")),
            explanation=ai_result.get("explanation"),
            modality_weights=ai_result.get("modality_weights"),
            fusion_method=ai_result.get("fusion_method"),
            blockchain_verified=blockchain_verified,
            blockchain_match=blockchain_match,
        )
        db.add(result)

        job.status = JobStatus.COMPLETED.value
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()

        return {
            "job_id": job_id,
            "verdict": ai_result["verdict"],
            "trust_score": ai_result["trust_score"],
        }

    except Exception as e:
        from celery.exceptions import SoftTimeLimitExceeded
        if job:
            if isinstance(e, SoftTimeLimitExceeded):
                job.error_message = "Analysis timed out after 270s. Try a shorter video."
            else:
                job.error_message = str(e)[:1000]
            job.status = JobStatus.FAILED.value
            db.commit()
        raise

    finally:
        db.close()
