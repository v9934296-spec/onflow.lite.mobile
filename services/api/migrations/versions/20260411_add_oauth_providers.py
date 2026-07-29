"""Add OAuth columns and indexes on users.

Revision ID: add_oauth_providers
Revises:
Create Date: 2026-04-11

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "add_oauth_providers"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}

    if "auth_provider" not in cols:
        op.add_column("users", sa.Column("auth_provider", sa.String(length=32), nullable=True))
    if "google_sub" not in cols:
        op.add_column("users", sa.Column("google_sub", sa.String(length=128), nullable=True))
    if "apple_sub" not in cols:
        op.add_column("users", sa.Column("apple_sub", sa.String(length=128), nullable=True))
    if "email_verified" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "bonus_analyses_granted" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "bonus_analyses_granted",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    if "bonus_analyses_used" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "bonus_analyses_used",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )

    ix = insp.get_indexes("users")
    ix_names = {i["name"] for i in ix if i.get("name")}
    dialect = conn.dialect.name

    if "ix_users_google_sub" not in ix_names:
        if dialect == "postgresql":
            op.create_index(
                "ix_users_google_sub",
                "users",
                ["google_sub"],
                unique=True,
                postgresql_where=sa.text("google_sub IS NOT NULL"),
            )
        else:
            op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    if "ix_users_apple_sub" not in ix_names:
        if dialect == "postgresql":
            op.create_index(
                "ix_users_apple_sub",
                "users",
                ["apple_sub"],
                unique=True,
                postgresql_where=sa.text("apple_sub IS NOT NULL"),
            )
        else:
            op.create_index("ix_users_apple_sub", "users", ["apple_sub"], unique=True)

    if dialect == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_users_email_lower ON users (lower((email)::text))"
        )


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_users_email_lower")

    for name in ("ix_users_apple_sub", "ix_users_google_sub"):
        try:
            op.drop_index(name, table_name="users")
        except Exception:
            pass

    insp = sa.inspect(conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    for col in (
        "bonus_analyses_used",
        "bonus_analyses_granted",
        "email_verified",
        "apple_sub",
        "google_sub",
        "auth_provider",
    ):
        if col in cols:
            op.drop_column("users", col)
