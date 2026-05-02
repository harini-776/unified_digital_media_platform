from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class SignalBreakdown(BaseModel):
    face_score: float | None = None
    lipsync_score: float | None = None
    voice_score: float | None = None
    blink_score: float | None = None
    headmotion_score: float | None = None
    details: dict | None = None


class BlockchainStatus(BaseModel):
    verified: bool | None = None
    match: bool | None = None
    tx_hash: str | None = None
    ipfs_cid: str | None = None
    network: str | None = None


class AnalysisResultResponse(BaseModel):
    id: UUID
    job_id: UUID
    video_id: UUID
    # Core outputs
    fake_probability: float
    trust_score: int
    verdict: str
    confidence: float
    # New calibrated + uncertainty fields
    confidence_calibrated_probability: Optional[float] = None
    uncertainty_flag: Optional[str] = None         # LOW | MEDIUM | HIGH
    entropy: Optional[float] = None
    explanation: Optional[str] = None
    modality_weights: Optional[dict] = None
    fusion_method: Optional[str] = None
    # Per-signal breakdown
    signals: SignalBreakdown
    blockchain: BlockchainStatus
    created_at: datetime
    video_name: str | None = None
    share_url: str | None = None
