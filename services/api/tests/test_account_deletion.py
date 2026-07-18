from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.auth import issue_onflow_access_token


def test_delete_account_requires_auth(client: TestClient) -> None:
    r = client.delete("/api/v1/account")
    assert r.status_code == 401


def test_delete_account_202_and_session_invalidated(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = client.delete("/api/v1/account", headers=auth_headers)
    assert r.status_code == 202, r.text
    assert r.headers["Cache-Control"] == "no-store"
    assert r.json() == {
        "status": "queued",
        "message": "Account deletion queued. Your clips will be permanently removed within 24 hours.",
    }
    r2 = client.get("/api/v1/account/me", headers=auth_headers)
    assert r2.status_code == 401


def test_delete_account_idempotent_with_dev_bearer(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    uid = client.get("/api/v1/account/me", headers=auth_headers).json()["user_id"]
    dev = {"Authorization": f"Bearer dev:{uid}"}
    r1 = client.delete("/api/v1/account", headers=dev)
    assert r1.status_code == 202
    r2 = client.delete("/api/v1/account", headers=dev)
    assert r2.status_code == 202


def test_delete_account_invalidates_jwt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("ONFLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'jwt_del.db'}")
    monkeypatch.setenv("ONFLOW_UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setenv("ONFLOW_JWT_SECRET", "k" * 32)
    import app.core.database as database_module

    database_module._engine = None
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        sr = c.post("/api/v1/auth/session", json={"email": "jwt-del@onflow.test"})
        assert sr.status_code == 200
        uid = sr.json()["user_id"]
        token = issue_onflow_access_token(uid)
        headers = {"Authorization": f"Bearer {token}"}
        dr = c.delete("/api/v1/account", headers=headers)
        assert dr.status_code == 202
        mr = c.get("/api/v1/account/me", headers=headers)
        assert mr.status_code == 401


def test_delete_account_purges_v1_clips_sessions_feed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from datetime import datetime, timezone

    from sqlmodel import Session, select

    from app.core.database import get_engine
    from app.models import ClipModel, FeedEventModel, SkateSessionModel

    me = client.get("/api/v1/account/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = me.json()["user_id"]
    now = datetime.now(timezone.utc)

    with Session(get_engine()) as db:
        session_row = SkateSessionModel(
            id="sess-del-1",
            user_id=user_id,
            started_at=now,
            ended_at=now,
            created_at=now,
            updated_at=now,
        )
        clip_row = ClipModel(
            id="clip-del-1",
            user_id=user_id,
            session_id="sess-del-1",
            storage_key="clips/clip-del-1.mp4",
            storage_url="",
            upload_status="analyzed",
            created_at=now,
            updated_at=now,
        )
        feed_row = FeedEventModel(
            id="feed-del-1",
            user_id=user_id,
            event_type="session_recap",
            event_version="v1",
            skate_session_id="sess-del-1",
            payload_json="{}",
            generated_at=now,
            propagates_at=now,
            propagation_status="propagated",
        )
        db.add(session_row)
        db.add(clip_row)
        db.add(feed_row)
        db.commit()

    r = client.delete("/api/v1/account", headers=auth_headers)
    assert r.status_code == 202, r.text

    with Session(get_engine()) as db:
        assert db.exec(select(ClipModel).where(ClipModel.user_id == user_id)).first() is None
        assert (
            db.exec(select(SkateSessionModel).where(SkateSessionModel.user_id == user_id)).first()
            is None
        )
        assert (
            db.exec(select(FeedEventModel).where(FeedEventModel.user_id == user_id)).first() is None
        )


def test_delete_account_removes_pending_upload_objects(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    """Pending V1 clips have no clip_jobs row — storage must still be deleted."""
    from datetime import datetime, timezone
    from pathlib import Path

    from sqlmodel import Session

    from app.core.database import get_engine
    from app.models import ClipModel

    me = client.get("/api/v1/account/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = me.json()["user_id"]
    now = datetime.now(timezone.utc)
    storage_key = f"clips/{user_id}/pending-orphan.mp4"

    upload_dir = Path(client.app.state.upload_dir)
    dest = upload_dir / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"fake-pending-video")
    assert dest.is_file()

    with Session(get_engine()) as db:
        db.add(
            ClipModel(
                id="clip-pending-orphan",
                user_id=user_id,
                session_id=None,
                storage_key=storage_key,
                storage_url="",
                upload_status="pending",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()

    r = client.delete("/api/v1/account", headers=auth_headers)
    assert r.status_code == 202, r.text
    assert not dest.exists(), "pending upload object must be purged from object storage"


def test_delete_account_purges_retention_copies(
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    me = client.get("/api/v1/account/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = me.json()["user_id"]

    retained = tmp_path / "retained-delete"
    monkeypatch.setenv("ONFLOW_RETENTION_DIR", str(retained))
    get_settings.cache_clear()

    clip_dir = retained / user_id / "ollie"
    clip_dir.mkdir(parents=True)
    retained_file = clip_dir / "job-x.mp4"
    retained_file.write_bytes(b"retained")
    assert retained_file.is_file()

    r = client.delete("/api/v1/account", headers=auth_headers)
    assert r.status_code == 202, r.text
    assert not (retained / user_id).exists(), "retention dir for user must be removed"
