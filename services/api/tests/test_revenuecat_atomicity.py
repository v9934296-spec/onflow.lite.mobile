"""RevenueCat event deduplication and billing mutation atomicity."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _create_user(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/session", json={"email": email})
    assert response.status_code == 200, response.text
    return response.json()["user_id"]


def _post_event(
    client: TestClient,
    *,
    event_id: str,
    event_type: str,
    app_user_id: str,
    product_id: str,
) -> dict:
    response = client.post(
        "/api/v1/webhooks/revenuecat",
        json={
            "event": {
                "id": event_id,
                "type": event_type,
                "app_user_id": app_user_id,
                "product_id": product_id,
            }
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_reup_duplicate_credits_once(client: TestClient) -> None:
    user_id = _create_user(client, "rc-reup-once@onflow.test")

    first = _post_event(
        client,
        event_id="evt-reup-once",
        event_type="NON_RENEWING_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_reup_pack_399",
    )
    duplicate = _post_event(
        client,
        event_id="evt-reup-once",
        event_type="NON_RENEWING_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_reup_pack_399",
    )

    assert first["action"] == "reup_bonus_added"
    assert first["bonus_analyses"] == 3
    assert duplicate["action"] == "duplicate_event_ignored"
    assert client.app.state.db.get_bonus_analyses(user_id) == 3


def test_unknown_product_event_remains_replayable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    user_id = _create_user(client, "rc-product-replay@onflow.test")
    monkeypatch.setenv("ONFLOW_RC_PRO_PRODUCT_IDS", "onflow_pro_monthly")
    get_settings.cache_clear()

    ignored = _post_event(
        client,
        event_id="evt-product-replay",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_annual",
    )
    assert ignored["action"] == "ignored_unknown_product"

    monkeypatch.setenv(
        "ONFLOW_RC_PRO_PRODUCT_IDS",
        "onflow_pro_monthly,onflow_pro_annual",
    )
    get_settings.cache_clear()
    replay = _post_event(
        client,
        event_id="evt-product-replay",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_annual",
    )

    assert replay["action"] == "tier_set_pro"
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_mutation_failure_rolls_back_event_claim(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import revenuecat_events

    user_id = _create_user(client, "rc-atomic-rollback@onflow.test")
    original_mutate = revenuecat_events._mutate_user

    def _fail_after_event_claim(*_args: object, **_kwargs: object) -> int | None:
        raise RuntimeError("forced mutation failure")

    monkeypatch.setattr(revenuecat_events, "_mutate_user", _fail_after_event_claim)
    with pytest.raises(RuntimeError, match="forced mutation failure"):
        revenuecat_events.apply_revenuecat_mutation(
            event_id="evt-atomic-rollback",
            candidate_user_ids=[user_id],
            rc_customer_id=user_id,
            new_tier="pro",
        )

    assert client.app.state.db.get_user_tier(user_id) != "pro"

    monkeypatch.setattr(revenuecat_events, "_mutate_user", original_mutate)
    replay = revenuecat_events.apply_revenuecat_mutation(
        event_id="evt-atomic-rollback",
        candidate_user_ids=[user_id],
        rc_customer_id=user_id,
        new_tier="pro",
    )

    assert replay.duplicate is False
    assert replay.user_id == user_id
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_unknown_user_event_remains_replayable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("ONFLOW_RC_PRO_PRODUCT_IDS", "onflow_pro_monthly")
    get_settings.cache_clear()
    user_id = "rc-user-created-later"

    ignored = _post_event(
        client,
        event_id="evt-user-replay",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
    )
    assert ignored["action"] == "ignored_unknown_user_subscription"

    client.app.state.db.ensure_invite_claim_user(user_id, "free")
    replay = _post_event(
        client,
        event_id="evt-user-replay",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
    )

    assert replay["action"] == "tier_set_pro"
    assert client.app.state.db.get_user_tier(user_id) == "pro"
