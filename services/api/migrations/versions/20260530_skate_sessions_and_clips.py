"""Skating sessions (skate_sessions) and V1 clips table with session_id FK.

Revision ID: 20260530_skate_sessions_clips
Revises: 20260517_trick_stat_land_score
Create Date: 2026-05-30

The existing ``sessions`` table stores auth tokens (SessionModel). Skating
sessions live in ``skate_sessions`` to avoid a naming collision.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260530_skate_sessions_clips"
down_revision = "20260517_trick_stat_land_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    dialect = conn.dialect.name

    if not insp.has_table("skate_sessions"):
        op.create_table(
            "skate_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("spot_label", sa.Text(), nullable=True),
            sa.Column("focus_trick", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("breakthrough_note", sa.Text(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index(
            "idx_skate_sessions_user_id",
            "skate_sessions",
            ["user_id"],
            postgresql_where=sa.text("deleted_at IS NULL") if dialect == "postgresql" else None,
        )
        op.create_index(
            "idx_skate_sessions_user_started",
            "skate_sessions",
            ["user_id", "started_at"],
            postgresql_where=sa.text("deleted_at IS NULL") if dialect == "postgresql" else None,
        )

    if not insp.has_table("clips"):
        op.create_table(
            "clips",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=True),
            sa.Column("trick_id", sa.String(length=64), nullable=True),
            sa.Column("storage_key", sa.Text(), nullable=False),
            sa.Column("storage_url", sa.Text(), nullable=False, server_default=""),
            sa.Column("thumbnail_key", sa.Text(), nullable=True),
            sa.Column("thumbnail_url", sa.Text(), nullable=True),
            sa.Column("duration_seconds", sa.Float(), nullable=True),
            sa.Column("width_px", sa.Integer(), nullable=True),
            sa.Column("height_px", sa.Integer(), nullable=True),
            sa.Column("content_type", sa.String(length=64), nullable=True),
            sa.Column("size_bytes", sa.BigInteger(), nullable=True),
            sa.Column(
                "upload_status",
                sa.String(length=16),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("landed", sa.Boolean(), nullable=True),
            sa.Column("pte_rating", sa.Integer(), nullable=True),
            sa.Column("is_first_land", sa.Boolean(), nullable=False, server_default=sa.false() if dialect == "postgresql" else "0"),
            sa.Column("hidden_from_feed", sa.Boolean(), nullable=False, server_default=sa.false() if dialect == "postgresql" else "0"),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["session_id"], ["skate_sessions.id"]),
        )
        op.create_index(
            "idx_clips_session_id",
            "clips",
            ["session_id"],
            postgresql_where=sa.text("session_id IS NOT NULL") if dialect == "postgresql" else None,
        )
        op.create_index("idx_clips_user_id", "clips", ["user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("clips"):
        op.drop_index("idx_clips_user_id", table_name="clips")
        op.drop_index("idx_clips_session_id", table_name="clips")
        op.drop_table("clips")
    if insp.has_table("skate_sessions"):
        op.drop_index("idx_skate_sessions_user_started", table_name="skate_sessions")
        op.drop_index("idx_skate_sessions_user_id", table_name="skate_sessions")
        op.drop_table("skate_sessions")
