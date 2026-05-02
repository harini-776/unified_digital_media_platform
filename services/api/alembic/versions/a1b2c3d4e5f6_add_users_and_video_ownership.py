"""add users table + video ownership

Revision ID: a1b2c3d4e5f6
Revises: 0b885c5cbb43
Create Date: 2026-05-02 11:00:00.000000

This migration:
  1. Creates the `users` table.
  2. Inserts a `system@trustmedia.local` user (unloggable-in by design — the
     password_hash is a bcrypt of a fresh random secret that is never written
     anywhere, so no one can authenticate as this user).
  3. Adds `videos.user_id` as a nullable FK to users.
  4. Backfills every existing video to point at the system user.
  5. Alters `videos.user_id` to NOT NULL.

Safety: the upgrade asserts the post-upgrade row count of `videos` matches the
pre-upgrade count, so any data loss fails the migration loudly inside the same
transaction (auto-rollback) instead of corrupting the dev DB silently.

Tested against an empty schema. Before running on a populated dev DB:
    pg_dump deepfake_trust > pre_migration_backup.sql
    alembic upgrade head
"""
from typing import Sequence, Union
import secrets

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0b885c5cbb43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SYSTEM_USER_EMAIL = "system@trustmedia.local"


def _bcrypt_unloggable_hash() -> str:
    """Hash a fresh random secret. The plaintext is discarded — this account is
    unloggable-in by construction, but still has a valid bcrypt hash for schema
    integrity."""
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd.hash(secrets.token_urlsafe(48))


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. Insert the system user. ON CONFLICT DO NOTHING handles the case where
    # a previous failed migration already inserted it.
    bind.execute(
        sa.text(
            """
            INSERT INTO users (id, email, password_hash, role, is_active, created_at)
            VALUES (gen_random_uuid(), :email, :pw_hash, 'admin', TRUE, NOW())
            ON CONFLICT (email) DO NOTHING
            """
        ),
        {"email": SYSTEM_USER_EMAIL, "pw_hash": _bcrypt_unloggable_hash()},
    )

    # Pre-count for safety check.
    pre_count = bind.execute(sa.text("SELECT COUNT(*) FROM videos")).scalar() or 0

    # 3. Add nullable user_id FK to videos
    op.add_column(
        "videos",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_videos_user_id", "videos", ["user_id"])
    op.create_foreign_key(
        "fk_videos_user_id_users",
        "videos",
        "users",
        ["user_id"],
        ["id"],
    )

    # 4. Backfill all existing videos to the system user.
    bind.execute(
        sa.text(
            """
            UPDATE videos
            SET user_id = (SELECT id FROM users WHERE email = :email)
            WHERE user_id IS NULL
            """
        ),
        {"email": SYSTEM_USER_EMAIL},
    )

    # Sanity check: every video must now have an owner, and the row count must
    # be unchanged from before the upgrade.
    post_count = bind.execute(sa.text("SELECT COUNT(*) FROM videos")).scalar() or 0
    null_count = bind.execute(sa.text("SELECT COUNT(*) FROM videos WHERE user_id IS NULL")).scalar() or 0
    if post_count != pre_count:
        raise RuntimeError(
            f"videos row count changed during upgrade ({pre_count} -> {post_count}); aborting"
        )
    if null_count != 0:
        raise RuntimeError(
            f"backfill incomplete: {null_count} video(s) still have NULL user_id; aborting"
        )

    # 5. Now safe to make user_id NOT NULL.
    op.alter_column("videos", "user_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_videos_user_id_users", "videos", type_="foreignkey")
    op.drop_index("ix_videos_user_id", table_name="videos")
    op.drop_column("videos", "user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
