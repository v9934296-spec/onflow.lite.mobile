"""Add gemini_spend_daily table for daily Gemini cost-cap tracking.

Revision ID: 20260516_gemini_spend_daily
Revises: 20260515_runtime_parity
Create Date: 2026-05-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260516_gemini_spend_daily"
down_revision = "20260515_runtime_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("gemini_spend_daily"):
        return
    op.create_table(
        "gemini_spend_daily",
        sa.Column("spend_date", sa.String(length=10), primary_key=True),
        sa.Column("spend_usd_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("job_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("gemini_spend_daily"):
        op.drop_table("gemini_spend_daily")
