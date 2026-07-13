"""feed_events table for session_recap and future progression events.

Revision ID: 20260603_feed_events
Revises: 20260530_skate_sessions_clips
Create Date: 2026-06-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260603_feed_events"
down_revision = "20260530_skate_sessions_clips"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("feed_events"):
        return

    op.create_table(
        "feed_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("event_version", sa.String(length=32), nullable=False),
        sa.Column("skate_session_id", sa.String(length=36), nullable=True),
        sa.Column("trick_id", sa.String(length=64), nullable=True),
        sa.Column("clip_id", sa.String(length=36), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("propagates_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("propagation_status", sa.String(length=16), nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_feed_events_user_id", "feed_events", ["user_id"])
    op.create_index(
        "ix_feed_events_skate_session_recap",
        "feed_events",
        ["user_id", "skate_session_id", "event_type"],
        unique=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("feed_events"):
        return
    op.drop_index("ix_feed_events_skate_session_recap", table_name="feed_events")
    op.drop_index("ix_feed_events_user_id", table_name="feed_events")
    op.drop_table("feed_events")
