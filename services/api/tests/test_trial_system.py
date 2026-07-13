from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient


def test_new_session_initializes_trial_window(client: TestClient) -> None:
    response = client.post("/api/v1/auth/session", json={"email": "trial-user@onflow.test"})
    assert response.status_code == 200, response.text
    payload = response.json()
    user = client.app.state.db.get_user(payload["user_id"])
    assert user is not None
    assert user.tier == "trial"
    assert user.trial_started_at is not None
    assert user.trial_expires_at is not None
    assert user.trial_expires_at - user.trial_started_at == timedelta(days=7)
    assert user.subscription_status == "active"


def test_existing_session_does_not_reset_trial_window(client: TestClient) -> None:
    first = client.post("/api/v1/auth/session", json={"email": "trial-existing@onflow.test"})
    assert first.status_code == 200, first.text
    user_id = first.json()["user_id"]
    initial_user = client.app.state.db.get_user(user_id)
    assert initial_user is not None
    initial_started_at = initial_user.trial_started_at
    initial_expires_at = initial_user.trial_expires_at

    second = client.post("/api/v1/auth/session", json={"email": "trial-existing@onflow.test"})
    assert second.status_code == 200, second.text
    same_user = client.app.state.db.get_user(user_id)
    assert same_user is not None
    assert second.json()["user_id"] == user_id
    assert same_user.trial_started_at == initial_started_at
    assert same_user.trial_expires_at == initial_expires_at


def test_account_quota_includes_trial_fields(client: TestClient) -> None:
    session_response = client.post("/api/v1/auth/session", json={"email": "quota-trial@onflow.test"})
    assert session_response.status_code == 200, session_response.text
    token = session_response.json()["session_token"]

    quota = client.get(
        "/api/v1/account/quota",
        headers={"Authorization": "Bearer " + token},
    )
    assert quota.status_code == 200, quota.text
    body = quota.json()
    assert body["tier"] == "trial"
    assert body["analyses_remaining"] == -1
    assert body["trial_expires_at"] is not None
    assert body["subscription_status"] == "active"
    assert body["bonus_analyses"] == 0
    assert body["monthly_free_remaining"] is None
