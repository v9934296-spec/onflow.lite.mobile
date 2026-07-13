"""Composite indexes for hot-path clip_jobs / sessions queries.

Revision ID: 20260426_clip_job_indexes
Revises: 20260414_deletion
Create Date: 2026-04-26

Adds three composite indexes that turn Seq Scans into Index Scans on the
queries that fire on every list / poll / submit:

* ``ix_clip_jobs_user_updated`` — list_for_user (user_id, updated_at DESC)
* ``ix_clip_jobs_status_updated`` — list_resumable (status, updated_at)
* ``ix_clip_jobs_user_status`` — count_active_clip_jobs (user_id, status)

Plus ``ix_sessions_user_created`` (sessions table; Postgres-only guard so it
no-ops on SQLite envs that never ran the sessions migration path).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260426_clip_job_indexes"
down_revision = "20260414_deletion"
branch_labels = None
depends_on = None


def _existing_index_names(table: str) -> set[str]:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return set()
    return {ix.get("name") for ix in insp.get_indexes(table) if ix.get("name")}


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    dialect = conn.dialect.name

    if not insp.has_table("clip_jobs"):
        return

    existing = _existing_index_names("clip_jobs")

    # list_for_user: ORDER BY updated_at DESC WHERE user_id = ?
    if "ix_clip_jobs_user_updated" not in existing:
        if dialect == "postgresql":
            op.create_index(
                "ix_clip_jobs_user_updated",
                "clip_jobs",
                ["user_id", sa.text("updated_at DESC")],
                unique=False,
            )
        else:
            op.create_index(
                "ix_clip_jobs_user_updated",
                "clip_jobs",
                ["user_id", "updated_at"],
                unique=False,
            )

    # list_resumable: WHERE status IN ('pending','processing') ORDER BY updated_at
    if "ix_clip_jobs_status_updated" not in existing:
        op.create_index(
            "ix_clip_jobs_status_updated",
            "clip_jobs",
            ["status", "updated_at"],
            unique=False,
        )

    # count_active_clip_jobs: WHERE user_id = ? AND status IN ('pending','processing')
    if "ix_clip_jobs_user_status" not in existing:
        op.create_index(
            "ix_clip_jobs_user_status",
            "clip_jobs",
            ["user_id", "status"],
            unique=False,
        )

    # sessions(user_id, created_at) — only if the table exists in this DB.
    if insp.has_table("sessions"):
        sessions_existing = _existing_index_names("sessions")
        if "ix_sessions_user_created" not in sessions_existing:
            op.create_index(
                "ix_sessions_user_created",
                "sessions",
                ["user_id", "created_at"],
                unique=False,
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("sessions"):
        for name in ("ix_sessions_user_created",):
            try:
                op.drop_index(name, table_name="sessions")
            except Exception:
                pass

    if not insp.has_table("clip_jobs"):
        return
    for name in (
        "ix_clip_jobs_user_status",
        "ix_clip_jobs_status_updated",
        "ix_clip_jobs_user_updated",
    ):
        try:
            op.drop_index(name, table_name="clip_jobs")
        except Exception:
            pass
