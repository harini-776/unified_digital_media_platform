import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class BlockchainRecord(Base):
    __tablename__ = "blockchain_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_hash: Mapped[str] = mapped_column(String(128), index=True)
    ipfs_cid: Mapped[str] = mapped_column(String(256), index=True)
    tx_hash: Mapped[str] = mapped_column(String(128), unique=True)
    block_number: Mapped[int | None] = mapped_column(nullable=True)
    network: Mapped[str] = mapped_column(String(64), default="polygon-amoy")
    owner_address: Mapped[str] = mapped_column(String(64))
    device_signature: Mapped[str | None] = mapped_column(String(256), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
