"""BE-001 — attempt-sync immutability: account-scoped uniqueness for attempts.

The sync endpoint used to upsert, so replaying a stale queued row could rewrite
the skater's manual outcome, move an attempt to a different session, or clear
``deleted_at`` and resurrect a removed one. The endpoint is now an immutable
replay contract; this migration records the invariant that contract relies on.

``session_attempts.id`` is already the primary key, so global uniqueness holds
without this index. The composite constraint makes the *account-scoped* rule
explicit: one attempt id per user. If a future migration ever widens the primary
key, this index is what keeps two owners from claiming the same attempt id.

Backwards compatible: additive index only, no column or type change, so the
currently deployed onflow-lite client keeps working unchanged.

Revision ID: 20260804_attempt_sync_immutability
Revises: 20260803_merge_heads
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260804_attempt_sync_immutability"
down_revision = "20260803_merge_heads"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_session_attempts_user_attempt"
TABLE_NAME = "session_attempts"


def _has_index(conn: sa.engine.Connection, name: str) -> bool:
    inspector = sa.inspect(conn)
    if not inspector.has_table(TABLE_NAME):
        return False
    return any(ix["name"] == name for ix in inspector.get_indexes(TABLE_NAME))


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(TABLE_NAME):
        return
    if _has_index(conn, INDEX_NAME):
        return

    # PostgreSQL: build without holding a write lock on the table. CONCURRENTLY
    # cannot run inside a transaction, so it needs its own connection.
    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.create_index(
                INDEX_NAME,
                TABLE_NAME,
                ["user_id", "id"],
                unique=True,
                postgresql_concurrently=True,
            )
        return

    op.create_index(INDEX_NAME, TABLE_NAME, ["user_id", "id"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    if not _has_index(conn, INDEX_NAME):
        return
    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(
                INDEX_NAME, table_name=TABLE_NAME, postgresql_concurrently=True
            )
        return
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
