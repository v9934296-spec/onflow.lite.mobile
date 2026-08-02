"""Add RevenueCat entitlement ordering state.

Revision ID: 20260802_rc_entitlement_state
Revises: 20260717_session_attempts
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_rc_entitlement_state"
down_revision = "20260717_session_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("rc_entitlement_state"):
        return
    op.create_table(
        "rc_entitlement_state",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("last_event_timestamp_ms", sa.BigInteger(), nullable=True),
        sa.Column("last_event_id", sa.String(length=256), nullable=True),
        sa.Column("last_tier", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("rc_entitlement_state"):
        op.drop_table("rc_entitlement_state")
