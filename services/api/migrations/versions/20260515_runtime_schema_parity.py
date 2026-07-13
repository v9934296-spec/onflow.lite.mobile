"""Columns previously added only by runtime helpers in database.py.

Revision ID: 20260515_runtime_parity
Revises: 20260509_user_created
Create Date: 2026-05-15

Idempotent adds for databases that relied on startup ALTER TABLE helpers.
After this migration, schema changes must go through Alembic only.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260515_runtime_parity"
down_revision = "20260509_user_created"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    insp = sa.inspect(conn)

    # --- trick_stats progression columns ---
    if insp.has_table("trick_stats"):
        cols = _cols("trick_stats")
        if "primary_issue_key" not in cols:
            op.add_column("trick_stats", sa.Column("primary_issue_key", sa.String(), nullable=True))
        if "primary_issue_label" not in cols:
            op.add_column("trick_stats", sa.Column("primary_issue_label", sa.String(), nullable=True))
        if "best_cue" not in cols:
            op.add_column("trick_stats", sa.Column("best_cue", sa.Text(), nullable=True))
        if "best_drill" not in cols:
            op.add_column("trick_stats", sa.Column("best_drill", sa.Text(), nullable=True))
        if "review_method" not in cols:
            op.add_column(
                "trick_stats",
                sa.Column(
                    "review_method",
                    sa.String(),
                    nullable=False,
                    server_default="first_pass_only",
                ),
            )
        if "gemini_used" not in cols:
            op.add_column(
                "trick_stats",
                sa.Column(
                    "gemini_used",
                    sa.Boolean() if dialect == "postgresql" else sa.Integer(),
                    nullable=False,
                    server_default=sa.false() if dialect == "postgresql" else "0",
                ),
            )
        if "session_id" not in cols:
            op.add_column("trick_stats", sa.Column("session_id", sa.String(), nullable=True))
        if "technical_limit_summary" not in cols:
            op.add_column(
                "trick_stats",
                sa.Column("technical_limit_summary", sa.Text(), nullable=True),
            )

    # --- clip_jobs quota tracking ---
    if insp.has_table("clip_jobs"):
        cols = _cols("clip_jobs")
        if "quota_source" not in cols:
            op.add_column("clip_jobs", sa.Column("quota_source", sa.String(), nullable=True))

    # --- users columns not in add_oauth_providers migration ---
    if insp.has_table("users"):
        cols = _cols("users")
        if "rc_customer_id" not in cols:
            op.add_column("users", sa.Column("rc_customer_id", sa.String(length=128), nullable=True))
        if "bonus_analyses" not in cols:
            op.add_column(
                "users",
                sa.Column(
                    "bonus_analyses",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )
        if "clip_retention_consent" not in cols:
            op.add_column(
                "users",
                sa.Column(
                    "clip_retention_consent",
                    sa.Boolean() if dialect == "postgresql" else sa.Integer(),
                    nullable=False,
                    server_default=sa.false() if dialect == "postgresql" else "0",
                ),
            )
        if "clip_retention_consent_at" not in cols:
            op.add_column(
                "users",
                sa.Column("clip_retention_consent_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "profile_image_url" not in cols:
            op.add_column("users", sa.Column("profile_image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("users"):
        cols = _cols("users")
        for col in (
            "profile_image_url",
            "clip_retention_consent_at",
            "clip_retention_consent",
            "bonus_analyses",
            "rc_customer_id",
        ):
            if col in cols:
                op.drop_column("users", col)

    if insp.has_table("clip_jobs"):
        cols = _cols("clip_jobs")
        if "quota_source" in cols:
            op.drop_column("clip_jobs", "quota_source")

    if insp.has_table("trick_stats"):
        cols = _cols("trick_stats")
        for col in (
            "technical_limit_summary",
            "session_id",
            "gemini_used",
            "review_method",
            "best_drill",
            "best_cue",
            "primary_issue_label",
            "primary_issue_key",
        ):
            if col in cols:
                op.drop_column("trick_stats", col)
