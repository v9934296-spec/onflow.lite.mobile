"""BE-004 — persist clip capture time across initiate → complete.

Ended-session uploads are accepted only when capture predates ``ended_at``.
Initiate already received ``captured_at`` from the launch client, but complete
used ``clips.created_at`` (initiate time). That rejected a legal delayed upload
after the session had ended. Persisting nullable ``captured_at`` lets complete
reuse the instant initiate already validated. NULL keeps the onflow-lite
window-only path.

Revision ID: 20260824_clips_captured_at
Revises: 20260804_attempt_sync_immutability
Create Date: 2026-08-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260824_clips_captured_at"
down_revision = "20260804_attempt_sync_immutability"
branch_labels = None
depends_on = None

TABLE_NAME = "clips"
COLUMN_NAME = "captured_at"


def _columns_for(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(TABLE_NAME):
        return
    if COLUMN_NAME in _columns_for(inspector, TABLE_NAME):
        return
    op.add_column(
        TABLE_NAME,
        sa.Column(COLUMN_NAME, sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(TABLE_NAME):
        return
    if COLUMN_NAME not in _columns_for(inspector, TABLE_NAME):
        return
    op.drop_column(TABLE_NAME, COLUMN_NAME)
