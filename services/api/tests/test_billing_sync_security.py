"""Billing sync must never grant entitlements from client claims.

The RevenueCat webhook is the single source of truth. POST /api/v1/billing/sync only
links the RC customer id and reads current state — a signed-in user cannot self-upgrade
to a paid tier or self-credit Re-Up bonus analyses by lying in the request body.
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_free_user(client: TestClient, user_id: str = "test-user-001") -> None:
    client.app.state.db.ensure_invite_claim_user(user_id, "free")


def test_client_cannot_self_upgrade_tier(authed_client: TestClient) -> None:
    _seed_free_user(authed_client)
    db = authed_client.app.state.db
    assert db.get_user_tier("test-user-001") == "free"

    resp = authed_client.post(
        "/api/v1/billing/sync",
        json={"has_pro": True, "sync_tier": "pro", "bonus_purchased": 12},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Response reflects real (free) state, not the client's claim.
    assert body["tier"] == "free"
    assert body["bonus_analyses"] == 0
    # And the database itself was not mutated by the client claim.
    assert db.get_user_tier("test-user-001") == "free"
    assert db.get_bonus_analyses("test-user-001") == 0


def test_client_cannot_self_credit_bonus(authed_client: TestClient) -> None:
    _seed_free_user(authed_client)
    db = authed_client.app.state.db

    # Repeated syncs claiming a bonus purchase must not accumulate credits.
    for _ in range(3):
        resp = authed_client.post(
            "/api/v1/billing/sync", json={"has_pro": False, "bonus_purchased": 12}
        )
        assert resp.status_code == 200, resp.text

    assert db.get_bonus_analyses("test-user-001") == 0


def test_sync_links_rc_customer_without_changing_tier(authed_client: TestClient) -> None:
    _seed_free_user(authed_client)
    db = authed_client.app.state.db

    resp = authed_client.post(
        "/api/v1/billing/sync",
        json={"has_pro": True, "rc_app_user_id": "rc-customer-xyz"},
    )
    assert resp.status_code == 200, resp.text

    # RC id is linked (so future webhooks resolve this user) but tier stays free.
    assert db.get_user_by_rc_customer("rc-customer-xyz") == "test-user-001"
    assert db.get_user_tier("test-user-001") == "free"
    assert resp.json()["tier"] == "free"
