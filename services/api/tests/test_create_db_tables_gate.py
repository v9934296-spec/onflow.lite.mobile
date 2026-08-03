"""create_db_tables must not mask missing Alembic migrations in prod/staging."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core import database as database_mod
from app.core.config import get_settings


def _deployed_env(monkeypatch: pytest.MonkeyPatch, env: str) -> None:
    monkeypatch.setenv("ONFLOW_ENV", env)
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.setenv("ONFLOW_DATABASE_URL", "postgresql://user:pass@localhost/onflow")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops@onflow.test")
    monkeypatch.setenv("ONFLOW_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-tl")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-s3-secret")
    monkeypatch.setenv("ONFLOW_RC_WEBHOOK_SECRET", "rc-webhook-test-secret")
    monkeypatch.setenv(
        "ONFLOW_RC_PRO_PRODUCT_IDS",
        "com.onflow.lite.lifetime,com.onflow.lite.yearly,com.onflow.lite.monthly",
    )
    get_settings.cache_clear()


@pytest.mark.parametrize("env", ["production", "staging"])
def test_create_db_tables_skipped_in_deployed_envs(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    _deployed_env(monkeypatch, env)
    create_all = MagicMock()
    monkeypatch.setattr(database_mod.SQLModel.metadata, "create_all", create_all)
    database_mod.create_db_tables()
    create_all.assert_not_called()
    get_settings.cache_clear()


def test_create_db_tables_runs_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "development")
    get_settings.cache_clear()
    create_all = MagicMock()
    monkeypatch.setattr(database_mod.SQLModel.metadata, "create_all", create_all)
    database_mod.create_db_tables()
    create_all.assert_called_once()
    get_settings.cache_clear()
