import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class Verdict(str, enum.Enum):
    AUTHENTIC = "authentic"
    SUSPICIOUS = "suspicious"
    MANIPULATED = "manipulated"


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"), unique=True)
    fake_probability: Mapped[float] = mapped_column(Float)
    trust_score: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)

    # Individual signal scores (JSON for flexibility)
    face_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    lipsync_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    voice_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    blink_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    headmotion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Calibration + uncertainty
    confidence_calibrated_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty_flag: Mapped[str | None] = mapped_column(String(8), nullable=True)
    entropy: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(String(512), nullable=True)
    modality_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fusion_method: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Blockchain verification
    blockchain_verified: Mapped[bool | None] = mapped_column(nullable=True)
    blockchain_match: Mapped[bool | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("AnalysisJob", back_populates="result")
