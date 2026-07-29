"""friendships table for mutual friend graph.

Revision ID: 20260614_friendships
Revises: 20260603b_feed_events_unique
Create Date: 2026-06-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_friendships"
down_revision = "20260603b_feed_events_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("friendships"):
        return

    op.create_table(
        "friendships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("requester_id", sa.String(length=64), nullable=False),
        sa.Column("addressee_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["addressee_id"], ["users.id"]),
        sa.CheckConstraint(
            "requester_id != addressee_id",
            name="ck_friendships_no_self_request",
        ),
    )
    op.create_index("ix_friendships_requester_id", "friendships", ["requester_id"])
    op.create_index("ix_friendships_addressee_id", "friendships", ["addressee_id"])
    op.create_index("ix_friendships_status", "friendships", ["status"])
    op.create_index("ix_friendships_created_at", "friendships", ["created_at"])
    op.create_index(
        "uq_friendships_requester_addressee_active",
        "friendships",
        ["requester_id", "addressee_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("friendships"):
        return
    op.drop_index("uq_friendships_requester_addressee_active", table_name="friendships")
    op.drop_index("ix_friendships_created_at", table_name="friendships")
    op.drop_index("ix_friendships_status", table_name="friendships")
    op.drop_index("ix_friendships_addressee_id", table_name="friendships")
    op.drop_index("ix_friendships_requester_id", table_name="friendships")
    op.drop_table("friendships")
