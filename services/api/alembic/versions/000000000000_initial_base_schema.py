"""initial_base_schema

Revision ID: 000000000000
Revises:
Create Date: 2026-05-02 11:50:00.000000

Creates the original base tables (videos, analysis_jobs, analysis_results,
blockchain_records) that previously came from `Base.metadata.create_all` at
app startup. The next migration (0b885c5cbb43) adds new ML columns on top of
analysis_results, so this base must run first.

Schema reflects the state *before* 0b885c5cbb43 — i.e. analysis_results does
NOT yet have headmotion_score, confidence_calibrated_probability, etc. Those
are added in the next migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "000000000000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "videos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("original_name", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("ipfs_cid", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_videos_file_hash", "videos", ["file_hash"])

    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("videos.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String(length=256), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "analysis_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id"), unique=True, nullable=False),
        sa.Column("fake_probability", sa.Float(), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("face_score", sa.Float(), nullable=True),
        sa.Column("lipsync_score", sa.Float(), nullable=True),
        sa.Column("voice_score", sa.Float(), nullable=True),
        sa.Column("blink_score", sa.Float(), nullable=True),
        sa.Column("signal_details", sa.JSON(), nullable=True),
        sa.Column("blockchain_verified", sa.Boolean(), nullable=True),
        sa.Column("blockchain_match", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "blockchain_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_hash", sa.String(length=128), nullable=False),
        sa.Column("ipfs_cid", sa.String(length=256), nullable=False),
        sa.Column("tx_hash", sa.String(length=128), unique=True, nullable=False),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("network", sa.String(length=64), nullable=False, server_default="polygon-amoy"),
        sa.Column("owner_address", sa.String(length=64), nullable=False),
        sa.Column("device_signature", sa.String(length=256), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_blockchain_records_video_hash", "blockchain_records", ["video_hash"])
    op.create_index("ix_blockchain_records_ipfs_cid", "blockchain_records", ["ipfs_cid"])


def downgrade() -> None:
    op.drop_index("ix_blockchain_records_ipfs_cid", table_name="blockchain_records")
    op.drop_index("ix_blockchain_records_video_hash", table_name="blockchain_records")
    op.drop_table("blockchain_records")
    op.drop_table("analysis_results")
    op.drop_table("analysis_jobs")
    op.drop_index("ix_videos_file_hash", table_name="videos")
    op.drop_table("videos")
