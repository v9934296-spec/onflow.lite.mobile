"""Keep ``alembic_version.version_num`` wide enough for this chain's revision IDs.

Alembic 1.13–1.18 create ``version_num VARCHAR(32)`` and expose no
``context.configure`` knob to change that. ``20260804_attempt_sync_immutability``
is 34 characters, so Postgres rejects the version-table UPDATE after that
revision's ``upgrade()`` and Railway ``preDeployCommand`` fails.

This helper runs from ``env.py`` *before* ``run_migrations``:

* missing table → create ``VARCHAR(64)`` so Alembic's ``checkfirst`` reuses it
* existing narrower column (production today) → ``ALTER … TYPE VARCHAR(64)``
* already wide enough → no-op

SQLite does not enforce ``VARCHAR`` length; CREATE-if-missing still runs so
tests share one path. ALTER is Postgres-only.
"""

from __future__ import annotations

from typing import Final

import sqlalchemy as sa
from sqlalchemy.engine import Connection

VERSION_TABLE: Final[str] = "alembic_version"
VERSION_COLUMN: Final[str] = "version_num"
VERSION_NUM_MAX_LEN: Final[int] = 64


def _column_length(connection: Connection) -> int | None:
    inspector = sa.inspect(connection)
    if not inspector.has_table(VERSION_TABLE):
        return None
    for column in inspector.get_columns(VERSION_TABLE):
        if column["name"] != VERSION_COLUMN:
            continue
        return getattr(column["type"], "length", None)
    return None


def ensure_alembic_version_num_width(
    connection: Connection,
    *,
    length: int = VERSION_NUM_MAX_LEN,
) -> None:
    """Create or widen ``alembic_version.version_num`` to ``length`` characters."""
    current = _column_length(connection)
    dialect = connection.dialect.name

    if current is None:
        connection.execute(
            sa.text(
                f"CREATE TABLE {VERSION_TABLE} ("
                f"{VERSION_COLUMN} VARCHAR({length}) NOT NULL, "
                f"CONSTRAINT {VERSION_TABLE}_pkc PRIMARY KEY ({VERSION_COLUMN}))"
            )
        )
        connection.commit()
        return

    if current >= length:
        return

    if dialect == "postgresql":
        connection.execute(
            sa.text(
                f"ALTER TABLE {VERSION_TABLE} "
                f"ALTER COLUMN {VERSION_COLUMN} TYPE VARCHAR({length})"
            )
        )
        connection.commit()
