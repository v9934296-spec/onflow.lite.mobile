"""Add land_score to trick_stats.

Revision ID: 20260517_trick_stat_land_score
Revises: 20260516_gemini_spend_daily
Create Date: 2026-05-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260517_trick_stat_land_score"
down_revision = "20260516_gemini_spend_daily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("trick_stats"):
        return
    cols = {c["name"] for c in insp.get_columns("trick_stats")}
    if "land_score" not in cols:
        op.add_column("trick_stats", sa.Column("land_score", sa.Float(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("trick_stats"):
        return
    cols = {c["name"] for c in insp.get_columns("trick_stats")}
    if "land_score" in cols:
        op.drop_column("trick_stats", "land_score")
