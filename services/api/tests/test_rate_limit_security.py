"""Route rate limits (slowapi) and abuse caps — separate from product quota and Gemini tier routing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import Settings
from app.core.database import get_engine
from app.core.tiers import resolve_gemini_model_for_tier
from app.models import ClipJobModel


from tests.conftest import write_presigned_upload


def _app_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, production: bool = False
) -> TestClient:
    monkeypatch.setenv("ONFLOW_ENV", "production" if production else "development")
    monkeypatch.setenv("ONFLOW_DATABASE_URL", f"sqlite:///{(tmp_path / 'rl.db').as_posix()}")
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "10000")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    if production:
        monkeypatch.setenv("ONFLOW_REDIS_URL", "redis://127.0.0.1:6379/0")
        monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
        monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
        monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
        monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
        monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
        monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
        monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")
        monkeypatch.setenv("ONFLOW_RC_WEBHOOK_SECRET", "rc-webhook-test-secret")
        monkeypatch.setenv(
            "ONFLOW_RC_PRO_PRODUCT_IDS",
            "com.onflow.lite.lifetime,com.onflow.lite.yearly,com.onflow.lite.monthly",
        )
        monkeypatch.setenv("ONFLOW_ALLOW_CREATE_ALL", "1")
    else:
        monkeypatch.delenv("ONFLOW_REDIS_URL", raising=False)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    return TestClient(create_app())


def _session_headers(c: TestClient) -> dict[str, str]:
    r = c.post("/api/v1/auth/session", json={"email": "rlimit@onflow.test"})
    assert r.status_code == 200, r.text
    tok = r.json()["session_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_auth_claim_rate_limited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invite claim was removed; session auth still shares the invite IP rate-limit helpers."""
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_HOUR", "100")
    with _app_client(tmp_path, monkeypatch) as c:
        r = c.post("/api/v1/auth/claim", json={"code": "ANYCODEHERE"})
        assert r.status_code == 404
        for i in range(2):
            r = c.post("/api/v1/auth/session", json={"email": f"claim-rl-{i}@t.com"})
            assert r.status_code == 200, r.text
        r3 = c.post("/api/v1/auth/session", json={"email": "claim-rl-3@t.com"})
        assert r3.status_code == 429


def test_session_rate_limited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("ONFLOW_AUTH_RATE_LIMIT_PER_HOUR", "100")
    with _app_client(tmp_path, monkeypatch) as c:
        for i in range(2):
            r = c.post("/api/v1/auth/session", json={"email": f"u{i}@t.com"})
            assert r.status_code == 200, r.text
        r3 = c.post("/api/v1/auth/session", json={"email": "u3@t.com"})
        assert r3.status_code == 429


def test_google_signin_rate_limited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_GOOGLE_CLIENT_IDS", "dummy-web-id")
    monkeypatch.setenv("ONFLOW_OAUTH_RATE_LIMIT_PER_MINUTE", "3")
    with _app_client(tmp_path, monkeypatch) as c:
        for _ in range(3):
            r = c.post("/api/v1/auth/google", json={"id_token": "x" * 20})
            assert r.status_code != 429
        r4 = c.post("/api/v1/auth/google", json={"id_token": "x" * 20})
        assert r4.status_code == 429


def test_apple_signin_rate_limited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_OAUTH_RATE_LIMIT_PER_MINUTE", "3")
    with _app_client(tmp_path, monkeypatch) as c:
        for _ in range(3):
            r = c.post("/api/v1/auth/apple", json={"id_token": "x" * 20})
            assert r.status_code != 429
        r4 = c.post("/api/v1/auth/apple", json={"id_token": "x" * 20})
        assert r4.status_code == 429


def test_account_export_rate_limited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_EXPORT_RATE_LIMIT_PER_HOUR", "2")
    with _app_client(tmp_path, monkeypatch) as c:
        h = _session_headers(c)
        for _ in range(2):
            r = c.get("/api/v1/account/export", headers=h)
            assert r.status_code == 200, r.text
        r3 = c.get("/api/v1/account/export", headers=h)
        assert r3.status_code == 429


def test_account_delete_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    """Destructive delete is capped per user id; idempotent retries do not hit this path."""
    monkeypatch.setenv("ONFLOW_DELETE_ACCOUNT_RATE_LIMIT_PER_DAY", "1")
    from app.core import rate_limit as rate_limit_module
    from app.core.rate_limit import enforce_delete_account_rate_limit

    # Force in-process path so the test is independent of any local Redis.
    monkeypatch.setattr(rate_limit_module, "_get_redis", lambda: None)
    monkeypatch.setattr(rate_limit_module, "_redis_client", None)

    uid = "rate-limit-delete-test-user"
    rate_limit_module._delete_account_hits[f"uid:{uid}"].clear()
    enforce_delete_account_rate_limit(uid)
    with pytest.raises(HTTPException) as ei:
        enforce_delete_account_rate_limit(uid)
    assert ei.value.status_code == 429
    assert "rate limit" in (ei.value.detail or "").lower()


def test_beta_client_events_rate_limited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_BETA_EVENT_RATE_LIMIT_PER_MINUTE", "2")
    with _app_client(tmp_path, monkeypatch) as c:
        h = _session_headers(c)
        body = {"kind": "result_viewed"}
        for _ in range(2):
            r = c.post("/api/v1/beta/client-events", headers=h, json=body)
            assert r.status_code == 200, r.text
        r3 = c.post("/api/v1/beta/client-events", headers=h, json=body)
        assert r3.status_code == 429


def test_webhook_lightweight_limit_does_not_replace_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wrong Authorization still 401 in production; throttle is additional."""
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.setenv("ONFLOW_WEBHOOK_RATE_LIMIT_PER_MINUTE", "500")
    with _app_client(tmp_path, monkeypatch, production=True) as c:
        r = c.post(
            "/api/v1/webhooks/revenuecat",
            json={},
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert r.status_code == 401


def test_clip_abuse_limits_are_config_driven_not_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: abuse caps are Settings fields, distinct from monthly free tier quota."""
    monkeypatch.setenv("ONFLOW_ENV", "development")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    s = Settings()
    assert s.clip_rate_limit_per_day >= 1
    assert s.clip_rate_limit_per_hour >= 1
    assert s.rate_limit_free != s.clip_rate_limit_per_day


def test_concurrent_processing_limit_returns_429(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cap is independent of product quota; seed one pending job (no race with async worker)."""
    monkeypatch.setenv("ONFLOW_CLIP_CONCURRENT_PROCESSING_LIMIT_PER_USER", "1")
    with _app_client(tmp_path, monkeypatch) as c:
        h = _session_headers(c)
        me = c.get("/api/v1/account/me", headers=h).json()
        uid = me["user_id"]
        now = datetime.now(timezone.utc)
        with Session(get_engine()) as session:
            session.add(
                ClipJobModel(
                    id="seed-pending-block",
                    user_id=uid,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                    input_reference="storage:seed",
                    clip_label="seed",
                    tier="free",
                    metadata_json="{}",
                )
            )
            session.commit()
        initiated = c.post(
            "/api/v1/clips/initiate-upload",
            headers=h,
            json={
                "duration_seconds": 4.5,
                "width_px": 1080,
                "height_px": 1920,
                "content_type": "video/mp4",
                "size_bytes": 1024,
            },
        )
        assert initiated.status_code == 201, initiated.text
        from app.services.video_signature import MINIMAL_VIDEO_SNIFF_BYTES

        write_presigned_upload(c, initiated.json()["storage_key"], MINIMAL_VIDEO_SNIFF_BYTES)
        r = c.post(
            f"/api/v1/clips/{initiated.json()['clip_id']}/complete-upload",
            headers=h,
        )
        assert r.status_code == 429, r.text
        assert "processing" in r.json()["detail"].lower()


def test_production_settings_require_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "staging")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.setenv("ONFLOW_DATABASE_URL", "postgresql://user:pass@localhost/onflow")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ONFLOW_RC_WEBHOOK_SECRET", "rc-webhook-test-secret")
    monkeypatch.setenv(
        "ONFLOW_RC_PRO_PRODUCT_IDS",
        "com.onflow.lite.lifetime,com.onflow.lite.yearly,com.onflow.lite.monthly",
    )
    monkeypatch.delenv("ONFLOW_REDIS_URL", raising=False)
    with pytest.raises(Exception) as exc:
        Settings()
    assert "ONFLOW_REDIS_URL" in str(exc.value)


def test_production_settings_reject_non_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_ENV", "production")
    monkeypatch.setenv("ONFLOW_ADMIN_EMAILS", "ops-admin@onflow.test")
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    monkeypatch.setenv("ONFLOW_DATABASE_URL", "postgresql://user:pass@localhost/onflow")
    monkeypatch.setenv("ONFLOW_TWELVELABS_API_KEY", "test-twelvelabs-key")
    monkeypatch.setenv("ONFLOW_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ONFLOW_S3_BUCKET", "onflow-clips")
    monkeypatch.setenv("ONFLOW_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("ONFLOW_S3_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("ONFLOW_S3_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ONFLOW_RC_WEBHOOK_SECRET", "rc-webhook-test-secret")
    monkeypatch.setenv(
        "ONFLOW_RC_PRO_PRODUCT_IDS",
        "com.onflow.lite.lifetime,com.onflow.lite.yearly,com.onflow.lite.monthly",
    )
    monkeypatch.setenv("ONFLOW_REDIS_URL", "memory://")
    with pytest.raises(Exception) as exc:
        Settings()
    assert "redis://" in str(exc.value).lower() or "rediss://" in str(exc.value).lower()


def test_rate_limit_storage_mode_exposed() -> None:
    from app.core.rate_limit import RATE_LIMIT_STORAGE, rate_limit_storage_mode

    assert rate_limit_storage_mode() == RATE_LIMIT_STORAGE
    assert rate_limit_storage_mode() in ("redis", "memory")


def test_pro_tier_gemini_routing_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier → model mapping must stay independent of rate-limit settings."""
    monkeypatch.setenv("ONFLOW_GEMINI_MODEL_FREE", "free-model-x")
    monkeypatch.setenv("ONFLOW_GEMINI_MODEL_PRO", "pro-model-y")
    s = Settings()
    assert resolve_gemini_model_for_tier("pro", s) == "pro-model-y"
    assert resolve_gemini_model_for_tier("free", s) == "free-model-x"


def test_bearer_identity_for_rate_limit_rejects_dev_token_in_staging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dev:`` tokens must not resolve to a rate-limit identity in staging.

    Every other production-guard check in core/auth.py (get_current_user,
    resolve_user_id_from_token, issue_onflow_access_token, ...) gates on
    ``is_production_or_staging``. This one used to check only ``is_production``,
    so a staging deploy would key rate limits off an unsigned dev token instead
    of falling back to IP — a drift bug, not exploitable auth bypass, but the
    kind that becomes one the next time a call site is copied without noticing.
    """
    import app.core.auth as auth_module

    class _FakeSettings:
        jwt_secret = ""
        is_production_or_staging = True

    class _FakeDb:
        def validate_token(self, token: str) -> str | None:
            return None

    class _FakeAppState:
        db = _FakeDb()

    class _FakeApp:
        state = _FakeAppState()

    class _FakeRequest:
        app = _FakeApp()

        def __init__(self, token: str) -> None:
            self._headers = {"authorization": f"Bearer {token}"}

        @property
        def headers(self):
            return self._headers

    monkeypatch.setattr(auth_module, "get_settings", lambda: _FakeSettings())

    uid = auth_module.bearer_identity_for_rate_limit(_FakeRequest("dev:someone"))
    assert uid is None
