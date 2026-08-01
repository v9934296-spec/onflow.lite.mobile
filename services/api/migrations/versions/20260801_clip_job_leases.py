"""Add clip job lease columns for exclusive worker ownership.

Revision ID: 20260801_clip_job_leases
Revises: 20260717_session_attempts
Create Date: 2026-08-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260801_clip_job_leases"
down_revision = "20260717_session_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("clip_jobs")}
    if "claim_token" not in cols:
        op.add_column(
            "clip_jobs",
            sa.Column("claim_token", sa.String(length=64), nullable=True),
        )
    if "claimed_at" not in cols:
        op.add_column(
            "clip_jobs",
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "lease_expires_at" not in cols:
        op.add_column(
            "clip_jobs",
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "attempt_number" not in cols:
        op.add_column(
            "clip_jobs",
            sa.Column(
                "attempt_number",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    op.drop_column("clip_jobs", "attempt_number")
    op.drop_column("clip_jobs", "lease_expires_at")
    op.drop_column("clip_jobs", "claimed_at")
    op.drop_column("clip_jobs", "claim_token")
