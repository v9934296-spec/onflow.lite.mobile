"""Schema bootstrap policy — Alembic only, no runtime ALTER helpers."""

from __future__ import annotations

from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

import app.core.database as database_module
from migrations.alembic_version_width import (
    VERSION_NUM_MAX_LEN,
    VERSION_TABLE,
    ensure_alembic_version_num_width,
)

_API_ROOT = Path(__file__).resolve().parents[1]
_ENV_PY = _API_ROOT / "migrations" / "env.py"


def _script() -> ScriptDirectory:
    return ScriptDirectory(str(_API_ROOT / "migrations"))


def _revision_ids() -> list[str]:
    return [script.revision for script in _script().walk_revisions()]


def test_no_runtime_migration_helpers_in_database_module() -> None:
    names = [n for n in dir(database_module) if n.startswith("_migrate_")]
    assert names == [], f"Remove runtime migrations; use Alembic: {names}"


def test_alembic_has_single_head_revision() -> None:
    heads = _script().get_heads()
    assert len(heads) == 1, f"Alembic must have exactly one head revision, found: {heads}"


def test_revision_ids_fit_supported_version_num_width() -> None:
    over = [rev for rev in _revision_ids() if len(rev) > VERSION_NUM_MAX_LEN]
    assert over == [], f"revision ids exceed VARCHAR({VERSION_NUM_MAX_LEN}): {over}"


def test_chain_has_revision_longer_than_alembic_default_32() -> None:
    """Lock the production failure: Alembic's default column is VARCHAR(32)."""
    long_ids = [rev for rev in _revision_ids() if len(rev) > 32]
    assert "20260804_attempt_sync_immutability" in long_ids
    assert len("20260804_attempt_sync_immutability") == 34


def test_env_widens_version_num_before_run_migrations() -> None:
    source = _ENV_PY.read_text(encoding="utf-8")
    online = source.split("def run_migrations_online", 1)[1]
    assert "ensure_alembic_version_num_width(connection)" in online
    assert online.index("ensure_alembic_version_num_width(connection)") < online.index(
        "context.run_migrations()"
    )


def test_ensure_creates_missing_version_table_at_supported_width() -> None:
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        ensure_alembic_version_num_width(connection)
        column = next(
            col
            for col in inspect(connection).get_columns(VERSION_TABLE)
            if col["name"] == "version_num"
        )
        assert getattr(column["type"], "length", None) == VERSION_NUM_MAX_LEN
        connection.execute(
            text(
                f"INSERT INTO {VERSION_TABLE} (version_num) "
                f"VALUES ('20260804_attempt_sync_immutability')"
            )
        )
        connection.commit()


def test_finalize_helper_exists_in_clip_worker() -> None:
    from app.services import clip_worker

    assert hasattr(clip_worker, "finalize_completed_clip_job")
    assert callable(clip_worker.finalize_completed_clip_job)
