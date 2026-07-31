"""Production fail-closed auth vs development convenience."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError


def _prod_db_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "prodsec.db"
    monkeypatch.setenv("ONFLOW_DATABASE_URL", f"sqlite:///{db.as_posix()}")
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "10000")
    # Satisfies production/staging Redis requirement for slowapi (connectivity check skipped in pytest).
    monkeypatch.setenv("ONFLOW_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key-not-used-in-requests")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key-not-used-in-requests")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")


def _prod_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimal env for Settings() in production/staging fail-closed tests."""
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.setenv("ONFLOW_DATABASE_URL", "postgresql://user:pass@localhost/onflow")
    monkeypatch.setenv("ONFLOW_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")
    monkeypatch.delenv("ONFLOW_TWELVELABS_API_KEY", raising=False)
    monkeypatch.delenv("ONFLOW_GEMINI_API_KEY", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()


def test_production_requires_redis_url_at_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    _prod_settings_env(monkeypatch)
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("ONFLOW_REDIS_URL", raising=False)
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_REDIS_URL" in str(exc.value)


def test_production_requires_jwt_secret_at_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.delenv("ONFLOW_JWT_SECRET", raising=False)
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_JWT_SECRET" in str(exc.value)


def test_production_session_route_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    # Avoid slowapi auth IP cap (5/min default) masking the production 403.
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_HOUR", "10000")
    _prod_db_env(tmp_path, monkeypatch)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    with TestClient(create_app()) as c:
        r = c.post("/api/v1/auth/session", json={"email": "anyone@example.com"})
        assert r.status_code == 403
        assert "production" in (r.json().get("detail") or "").lower()


def test_production_rejects_dev_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    _prod_db_env(tmp_path, monkeypatch)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    with TestClient(create_app()) as c:
        r = c.get(
            "/api/v1/stats/sessions/latest",
            headers={"Authorization": "Bearer dev:test-user-001"},
        )
        assert r.status_code == 401


def test_development_allows_dev_tokens_when_no_jwt_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "development")
    monkeypatch.delenv("ONFLOW_JWT_SECRET", raising=False)
    _prod_db_env(tmp_path, monkeypatch)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    with TestClient(create_app()) as c:
        r = c.get(
            "/api/v1/stats/sessions/latest",
            headers={"Authorization": "Bearer dev:test-user-001"},
        )
        assert r.status_code == 200


def test_production_webhook_requires_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.delenv("ONFLOW_RC_WEBHOOK_SECRET", raising=False)
    _prod_db_env(tmp_path, monkeypatch)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    with TestClient(create_app()) as c:
        r = c.post(
            "/api/v1/webhooks/revenuecat",
            json={"event": {"type": "INITIAL_PURCHASE", "app_user_id": "u1"}},
        )
        assert r.status_code == 401
        detail = (r.json().get("detail") or "").lower()
        assert "webhook" in detail or "authorization" in detail or "configured" in detail


def test_production_issue_onflow_access_token_never_dev_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "unit-test-jwt-secret-32-bytes-minimum")
    monkeypatch.setenv("ONFLOW_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")
    # Production fail-closed: must always set ONFLOW_DATABASE_URL.
    monkeypatch.setenv(
        "ONFLOW_DATABASE_URL", f"sqlite:///{(tmp_path / 'tok.db').as_posix()}"
    )
    from app.core.auth import issue_onflow_access_token

    token = issue_onflow_access_token("a" * 16)
    assert not token.startswith("dev:")
    assert token.count(".") == 2


def test_production_claim_invite_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "unit-test-jwt-secret-32-bytes-minimum")
    monkeypatch.setenv("ONFLOW_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")
    # Production fail-closed: must always set ONFLOW_DATABASE_URL.
    monkeypatch.setenv(
        "ONFLOW_DATABASE_URL", f"sqlite:///{(tmp_path / 'claim.db').as_posix()}"
    )
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "up"))
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    with TestClient(create_app()) as c:
        r = c.post("/api/v1/auth/claim", json={"code": "grind-01"})
        assert r.status_code == 404


def test_production_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production fail-closed: refuse to run on SQLite. Postgres-only via ONFLOW_DATABASE_URL."""
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.delenv("ONFLOW_DATABASE_URL", raising=False)
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_DATABASE_URL" in str(exc.value)


def test_staging_requires_admin_emails_at_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "staging")
    _prod_settings_env(monkeypatch)
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("ONFLOW_ADMIN_EMAILS", raising=False)
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_ADMIN_EMAILS" in str(exc.value)


def test_production_requires_admin_emails_at_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    _prod_settings_env(monkeypatch)
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("ONFLOW_ADMIN_EMAILS", raising=False)
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_ADMIN_EMAILS" in str(exc.value)


def test_development_allows_missing_admin_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "development")
    monkeypatch.delenv("ONFLOW_ADMIN_EMAILS", raising=False)
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert not (s.admin_emails or "").strip()


def test_staging_requires_twelvelabs_api_key_at_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "staging")
    _prod_settings_env(monkeypatch)
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_TWELVELABS_API_KEY" in str(exc.value)


def test_production_requires_twelvelabs_api_key_at_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    _prod_settings_env(monkeypatch)
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_TWELVELABS_API_KEY" in str(exc.value)


def test_production_requires_gemini_api_key_at_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    _prod_settings_env(monkeypatch)
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.delenv("ONFLOW_GEMINI_API_KEY", raising=False)
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_GEMINI_API_KEY" in str(exc.value)


def test_staging_requires_s3_at_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "staging")
    _prod_settings_env(monkeypatch)
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("ONFLOW_S3_BUCKET", raising=False)
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "ONFLOW_S3_BUCKET" in str(exc.value)


def test_development_allows_missing_twelvelabs_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "development")
    monkeypatch.delenv("ONFLOW_TWELVELABS_API_KEY", raising=False)
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert not (s.twelvelabs_api_key or "").strip()


def test_get_twelvelabs_api_key_returns_settings_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "tl-secret-never-log-xyz"
    monkeypatch.setenv("ONFLOW_ENV", "development")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", secret)
    from app.core.config import get_settings
    from app.core.twelvelabs_config import get_twelvelabs_api_key

    get_settings.cache_clear()
    assert get_twelvelabs_api_key() == secret


def test_twelvelabs_key_never_in_validation_error_or_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "tl-secret-never-log-xyz"
    monkeypatch.setenv("ONFLOW_ENV", "staging")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.setenv("ONFLOW_DATABASE_URL", "postgresql://user:pass@localhost/onflow")
    monkeypatch.setenv("ONFLOW_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", secret)
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")
    from app.core.config import Settings, get_settings
    from app.core.twelvelabs_config import get_twelvelabs_api_key

    get_settings.cache_clear()
    assert get_twelvelabs_api_key() == secret

    monkeypatch.delenv("ONFLOW_TWELVELABS_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    err_text = str(exc.value)
    assert "ONFLOW_TWELVELABS_API_KEY" in err_text
    assert secret not in err_text
    assert secret not in caplog.text
