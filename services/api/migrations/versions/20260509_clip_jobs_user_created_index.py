"""Composite index for sargable monthly quota query.

Revision ID: 20260509_user_created
Revises: 20260426_clip_job_indexes
Create Date: 2026-05-09

The monthly quota check (``count_monthly_free_jobs``) was rewritten from
``EXTRACT(year/month FROM created_at)`` predicates to a ``created_at`` range
filter so Postgres can actually use an index. To make that index exist, this
migration adds:

* ``ix_clip_jobs_user_created`` — ``(user_id, created_at)``

It only complements the existing indexes; ``ix_clip_jobs_user_updated`` cannot
serve the quota query because the predicate is on ``created_at``, not
``updated_at``.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_user_created"
down_revision = "20260426_clip_job_indexes"
branch_labels = None
depends_on = None


def _existing_index_names(table: str) -> set[str]:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return set()
    return {ix.get("name") for ix in insp.get_indexes(table) if ix.get("name")}


def upgrade() -> None:
    if "ix_clip_jobs_user_created" in _existing_index_names("clip_jobs"):
        return
    op.create_index(
        "ix_clip_jobs_user_created",
        "clip_jobs",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    if "ix_clip_jobs_user_created" not in _existing_index_names("clip_jobs"):
        return
    try:
        op.drop_index("ix_clip_jobs_user_created", table_name="clip_jobs")
    except Exception:
        pass
