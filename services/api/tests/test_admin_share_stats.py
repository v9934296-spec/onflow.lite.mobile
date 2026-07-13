"""Admin share funnel aggregates (Bearer auth + users.is_admin)."""

from __future__ import annotations


def test_share_stats_requires_auth(client) -> None:
    r = client.get("/api/v1/admin/share-stats")
    assert r.status_code == 401


def test_share_stats_requires_admin_role(authed_client) -> None:
    r = authed_client.get("/api/v1/admin/share-stats")
    assert r.status_code == 403


def test_share_stats_returns_shape(admin_client) -> None:
    r = admin_client.get("/api/v1/admin/share-stats?days=7")
    assert r.status_code == 200
    data = r.json()
    assert "share_initiated" in data
    assert "share_completed" in data
    assert "share_install_attributed" in data
    assert "completion_rate" in data
    assert data["window_days"] == 7


def test_share_stats_counts_after_client_event(admin_client) -> None:
    p = admin_client.post(
        "/api/v1/beta/client-events",
        json={
            "kind": "share_initiated",
            "job_id": "job-share-1",
            "share_target": "instagram_stories",
        },
    )
    assert p.status_code == 200
    c = admin_client.post(
        "/api/v1/beta/client-events",
        json={"kind": "share_completed", "job_id": "job-share-1", "share_target": "system"},
    )
    assert c.status_code == 200

    r = admin_client.get("/api/v1/admin/share-stats?days=7")
    assert r.status_code == 200
    body = r.json()
    assert body["share_initiated"] >= 1
    assert body["share_completed"] >= 1
    assert body["completion_rate"] > 0


def test_share_stats_allows_db_is_admin(client, monkeypatch) -> None:
    """users.is_admin set directly (no env bootstrap) also grants access."""
    monkeypatch.delenv("ONFLOW_ADMIN_EMAILS", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    session_resp = client.post(
        "/api/v1/auth/session",
        json={"email": "db-admin@onflow.test"},
    )
    assert session_resp.status_code == 200
    body = session_resp.json()
    user_id = body["user_id"]
    token = body["session_token"]

    db = client.app.state.db
    user = db.get_user(user_id)
    assert user is not None
    user.is_admin = True
    with db._sf() as session:
        session.add(user)
        session.commit()

    r = client.get(
        "/api/v1/admin/share-stats?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
