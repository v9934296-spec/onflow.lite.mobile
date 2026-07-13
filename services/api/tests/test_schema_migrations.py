"""Schema bootstrap policy — Alembic only, no runtime ALTER helpers."""

from __future__ import annotations

from pathlib import Path

from alembic.script import ScriptDirectory

import app.core.database as database_module


def test_no_runtime_migration_helpers_in_database_module() -> None:
    names = [n for n in dir(database_module) if n.startswith("_migrate_")]
    assert names == [], f"Remove runtime migrations; use Alembic: {names}"


def test_alembic_has_single_head_revision() -> None:
    api_root = Path(__file__).resolve().parents[1]
    script = ScriptDirectory(str(api_root / "migrations"))

    heads = script.get_heads()
    assert len(heads) == 1, f"Alembic must have exactly one head revision, found: {heads}"


def test_finalize_helper_exists_in_clip_worker() -> None:
    from app.services import clip_worker

    assert hasattr(clip_worker, "finalize_completed_clip_job")
    assert callable(clip_worker.finalize_completed_clip_job)
