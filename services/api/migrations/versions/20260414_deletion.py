"""Account deletion scheduling and token invalidation columns on users.

Revision ID: 20260414_deletion
Revises: 20260414_consent
Create Date: 2026-04-14

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_deletion"
down_revision = "20260414_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}

    if "pending_deletion_at" not in cols:
        op.add_column(
            "users",
            sa.Column("pending_deletion_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "hard_deleted_at" not in cols:
        op.add_column(
            "users",
            sa.Column("hard_deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "deletion_source" not in cols:
        op.add_column("users", sa.Column("deletion_source", sa.String(length=32), nullable=True))
    if "tokens_invalidated_at" not in cols:
        op.add_column(
            "users",
            sa.Column("tokens_invalidated_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    for col in (
        "tokens_invalidated_at",
        "deletion_source",
        "hard_deleted_at",
        "pending_deletion_at",
    ):
        if col in cols:
            op.drop_column("users", col)
