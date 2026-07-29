"""Unique partial index guarding one feed event per (user, session, type).

Revision ID: 20260603b_feed_events_unique
Revises: 20260603_feed_events
Create Date: 2026-06-03

Defense-in-depth for session_recap idempotency (Step 5D). The app layer checks
for an existing event before inserting; this index makes duplicates impossible
even under concurrent end-session calls.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260603b_feed_events_unique"
down_revision = "20260603_feed_events"
branch_labels = None
depends_on = None

_INDEX = "uq_feed_events_session_event"


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("feed_events"):
        return
    existing = {ix["name"] for ix in insp.get_indexes("feed_events")}
    if _INDEX in existing:
        return
    where = "deleted_at IS NULL AND skate_session_id IS NOT NULL"
    op.create_index(
        _INDEX,
        "feed_events",
        ["user_id", "skate_session_id", "event_type"],
        unique=True,
        sqlite_where=sa.text(where),
        postgresql_where=sa.text(where),
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("feed_events"):
        return
    existing = {ix["name"] for ix in insp.get_indexes("feed_events")}
    if _INDEX in existing:
        op.drop_index(_INDEX, table_name="feed_events")
