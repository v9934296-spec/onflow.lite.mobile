"""Misconfigured RevenueCat expiration events must remain replayable."""

import pytest
from fastapi.testclient import TestClient


def test_expiration_replays_after_product_allowlist_is_fixed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    session = client.post(
        "/api/v1/auth/session",
        json={"email": "rc-expiration-replay@onflow.test"},
    )
    assert session.status_code == 200, session.text
    user_id = session.json()["user_id"]
    client.app.state.db.set_user_tier(user_id, "pro")

    monkeypatch.setenv("ONFLOW_RC_PRO_PRODUCT_IDS", "onflow_pro_monthly")
    get_settings.cache_clear()
    payload = {
        "event": {
            "id": "evt-expiration-allowlist-replay",
            "type": "EXPIRATION",
            "app_user_id": user_id,
            "original_app_user_id": user_id,
            "aliases": [user_id],
            "product_id": "onflow_pro_annual",
            "event_timestamp_ms": 2_000,
        }
    }

    ignored = client.post("/api/v1/webhooks/revenuecat", json=payload)
    assert ignored.status_code == 200, ignored.text
    assert ignored.json()["action"] == "ignored_unknown_product"
    assert client.app.state.db.get_user_tier(user_id) == "pro"

    monkeypatch.setenv(
        "ONFLOW_RC_PRO_PRODUCT_IDS",
        "onflow_pro_monthly,onflow_pro_annual",
    )
    get_settings.cache_clear()
    replay = client.post("/api/v1/webhooks/revenuecat", json=payload)

    assert replay.status_code == 200, replay.text
    assert replay.json()["action"] == "tier_set_free"
    assert client.app.state.db.get_user_tier(user_id) == "free"
