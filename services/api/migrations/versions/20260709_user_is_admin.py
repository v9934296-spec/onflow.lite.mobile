"""Add users.is_admin for role-based admin access.

Revision ID: 20260709_user_is_admin
Revises: 20260702_trial_system
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260709_user_is_admin"
down_revision = "20260702_trial_system"
branch_labels = None
depends_on = None


def _columns_for(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table("users"):
        user_columns = _columns_for(inspector, "users")
        if "is_admin" not in user_columns:
            op.add_column(
                "users",
                sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table("users"):
        user_columns = _columns_for(inspector, "users")
        if "is_admin" in user_columns:
            op.drop_column("users", "is_admin")
