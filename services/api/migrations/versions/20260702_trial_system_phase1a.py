"""Add trial tracking fields and subscription events.

Revision ID: 20260702_trial_system
Revises: 20260614_friendships
Create Date: 2026-07-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260702_trial_system"
down_revision = "20260614_friendships"
branch_labels = None
depends_on = None


def _columns_for(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table("users"):
        user_columns = _columns_for(inspector, "users")
        if "trial_started_at" not in user_columns:
            op.add_column("users", sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True))
        if "trial_expires_at" not in user_columns:
            op.add_column("users", sa.Column("trial_expires_at", sa.DateTime(timezone=True), nullable=True))
        if "subscription_status" not in user_columns:
            op.add_column(
                "users",
                sa.Column("subscription_status", sa.String(length=32), nullable=False, server_default="active"),
            )
        if "subscription_product_id" not in user_columns:
            op.add_column("users", sa.Column("subscription_product_id", sa.String(length=128), nullable=True))
        if "rc_app_user_id" not in user_columns:
            op.add_column("users", sa.Column("rc_app_user_id", sa.String(length=128), nullable=True))
        if "reup_expires_at" not in user_columns:
            op.add_column("users", sa.Column("reup_expires_at", sa.DateTime(timezone=True), nullable=True))
        if "bonus_analyses" not in user_columns:
            op.add_column("users", sa.Column("bonus_analyses", sa.Integer(), nullable=False, server_default="0"))

    if not inspector.has_table("subscription_events"):
        op.create_table(
            "subscription_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("from_tier", sa.String(length=16), nullable=True),
            sa.Column("to_tier", sa.String(length=16), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
        )
        op.create_index(
            "ix_subscription_events_user_id",
            "subscription_events",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if inspector.has_table("subscription_events"):
        indexes = {idx["name"] for idx in inspector.get_indexes("subscription_events")}
        if "ix_subscription_events_user_id" in indexes:
            op.drop_index("ix_subscription_events_user_id", table_name="subscription_events")
        op.drop_table("subscription_events")

    if inspector.has_table("users"):
        user_columns = _columns_for(inspector, "users")
        if "reup_expires_at" in user_columns:
            op.drop_column("users", "reup_expires_at")
        if "rc_app_user_id" in user_columns:
            op.drop_column("users", "rc_app_user_id")
        if "subscription_product_id" in user_columns:
            op.drop_column("users", "subscription_product_id")
        if "subscription_status" in user_columns:
            op.drop_column("users", "subscription_status")
        if "trial_expires_at" in user_columns:
            op.drop_column("users", "trial_expires_at")
        if "trial_started_at" in user_columns:
            op.drop_column("users", "trial_started_at")
