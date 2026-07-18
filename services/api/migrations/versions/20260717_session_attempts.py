"""Add session_attempts table for server-side attempt log sync.

Revision ID: 20260717_session_attempts
Revises: 20260710_admin_role_events
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260717_session_attempts"
down_revision = "20260710_admin_role_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("session_attempts"):
        return
    op.create_table(
        "session_attempts",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("trick_id", sa.String(length=64), nullable=False),
        sa.Column("canonical_name", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["skate_sessions.id"]),
    )
    op.create_index("ix_session_attempts_user_id", "session_attempts", ["user_id"])
    op.create_index("ix_session_attempts_session_id", "session_attempts", ["session_id"])
    op.create_index(
        "ix_session_attempts_user_session",
        "session_attempts",
        ["user_id", "session_id"],
    )
    op.create_index(
        "ix_session_attempts_session_logged",
        "session_attempts",
        ["session_id", "logged_at"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table("session_attempts"):
        return
    op.drop_index("ix_session_attempts_session_logged", table_name="session_attempts")
    op.drop_index("ix_session_attempts_user_session", table_name="session_attempts")
    op.drop_index("ix_session_attempts_session_id", table_name="session_attempts")
    op.drop_index("ix_session_attempts_user_id", table_name="session_attempts")
    op.drop_table("session_attempts")
