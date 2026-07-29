"""Consent columns on users and consent_events audit table.

Revision ID: 20260414_consent
Revises: add_oauth_providers
Create Date: 2026-04-14

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260414_consent"
down_revision = "add_oauth_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}

    if "consent_granted_at" not in cols:
        op.add_column(
            "users",
            sa.Column("consent_granted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "consent_copy_version" not in cols:
        op.add_column("users", sa.Column("consent_copy_version", sa.String(length=32), nullable=True))
    if "consent_source" not in cols:
        op.add_column("users", sa.Column("consent_source", sa.String(length=32), nullable=True))

    if not insp.has_table("consent_events"):
        op.create_table(
            "consent_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("copy_version", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_consent_events_user_id"), "consent_events", ["user_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if insp.has_table("consent_events"):
        try:
            op.drop_index(op.f("ix_consent_events_user_id"), table_name="consent_events")
        except Exception:
            pass
        op.drop_table("consent_events")
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    for col in ("consent_source", "consent_copy_version", "consent_granted_at"):
        if col in cols:
            op.drop_column("users", col)
