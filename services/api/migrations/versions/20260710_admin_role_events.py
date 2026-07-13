"""Add admin_role_events audit table for is_admin promotions.

Revision ID: 20260710_admin_role_events
Revises: 20260709_user_is_admin
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260710_admin_role_events"
down_revision = "20260709_user_is_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("admin_role_events"):
        return
    op.create_table(
        "admin_role_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_admin_role_events_user_id",
        "admin_role_events",
        ["user_id"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if inspector.has_table("admin_role_events"):
        op.drop_index("ix_admin_role_events_user_id", table_name="admin_role_events")
        op.drop_table("admin_role_events")
