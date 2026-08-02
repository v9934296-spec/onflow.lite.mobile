"""RevenueCat event deduplication, replay, identity, and ordering safety."""

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
    event_timestamp_ms: int = 1_000,
    aliases: list[str] | None = None,
    original_app_user_id: str | None = None,
    subscriber_attributes: dict | None = None,
    expected_status: int = 200,
) -> dict:
    event: dict = {
        "id": event_id,
        "type": event_type,
        "app_user_id": app_user_id,
        "product_id": product_id,
        "event_timestamp_ms": event_timestamp_ms,
    }
    if aliases is not None:
        event["aliases"] = aliases
    if original_app_user_id is not None:
        event["original_app_user_id"] = original_app_user_id
    if subscriber_attributes is not None:
        event["subscriber_attributes"] = subscriber_attributes

    response = client.post(
        "/api/v1/webhooks/revenuecat",
        json={"event": event},
    )
    assert response.status_code == expected_status, response.text
    return response.json()


def _allow_pro_products(
    monkeypatch: pytest.MonkeyPatch,
    value: str = "onflow_pro_monthly,onflow_pro_annual",
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("ONFLOW_RC_PRO_PRODUCT_IDS", value)
    get_settings.cache_clear()


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


def test_unknown_product_event_remains_manually_replayable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = _create_user(client, "rc-product-replay@onflow.test")
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")

    ignored = _post_event(
        client,
        event_id="evt-product-replay",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_annual",
    )
    assert ignored["action"] == "ignored_unknown_product"

    _allow_pro_products(monkeypatch)
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
    original_apply = revenuecat_events._apply_product_entitlement_event

    def _fail_after_event_claim(*_args: object, **_kwargs: object) -> tuple[bool, str]:
        raise RuntimeError("forced mutation failure")

    monkeypatch.setattr(
        revenuecat_events,
        "_apply_product_entitlement_event",
        _fail_after_event_claim,
    )
    with pytest.raises(RuntimeError, match="forced mutation failure"):
        revenuecat_events.apply_revenuecat_mutation(
            event_id="evt-atomic-rollback",
            candidate_user_ids=[user_id],
            rc_customer_id=user_id,
            entitlement_product_id="onflow_pro_monthly",
            entitlement_active=True,
            pro_product_ids={"onflow_pro_monthly"},
            event_timestamp_ms=1_000,
        )

    assert client.app.state.db.get_user_tier(user_id) != "pro"

    monkeypatch.setattr(
        revenuecat_events,
        "_apply_product_entitlement_event",
        original_apply,
    )
    replay = revenuecat_events.apply_revenuecat_mutation(
        event_id="evt-atomic-rollback",
        candidate_user_ids=[user_id],
        rc_customer_id=user_id,
        entitlement_product_id="onflow_pro_monthly",
        entitlement_active=True,
        pro_product_ids={"onflow_pro_monthly"},
        event_timestamp_ms=1_000,
    )

    assert replay.duplicate is False
    assert replay.user_id == user_id
    assert replay.tier == "pro"
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_unknown_paid_user_requests_automatic_retry_and_remains_replayable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    user_id = "rc-user-created-later"

    failed = _post_event(
        client,
        event_id="evt-user-replay",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        expected_status=503,
    )
    assert "retry" in failed["detail"].lower()

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


def test_alias_resolves_anonymous_revenuecat_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    user_id = _create_user(client, "rc-alias@onflow.test")

    result = _post_event(
        client,
        event_id="evt-alias-resolve",
        event_type="INITIAL_PURCHASE",
        app_user_id="$RCAnonymousID:abc123",
        product_id="onflow_pro_monthly",
        aliases=["$RCAnonymousID:abc123", user_id],
    )

    assert result["action"] == "tier_set_pro"
    assert result["user_id"] == user_id
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_original_app_user_id_resolves_account(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    user_id = _create_user(client, "rc-original-id@onflow.test")

    result = _post_event(
        client,
        event_id="evt-original-id",
        event_type="INITIAL_PURCHASE",
        app_user_id="$RCAnonymousID:current",
        original_app_user_id=user_id,
        product_id="onflow_pro_monthly",
    )

    assert result["action"] == "tier_set_pro"
    assert result["user_id"] == user_id


def test_client_subscriber_attribute_cannot_redirect_entitlement(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    buyer_id = _create_user(client, "rc-real-buyer@onflow.test")
    victim_id = _create_user(client, "rc-attribute-victim@onflow.test")

    result = _post_event(
        client,
        event_id="evt-untrusted-attribute",
        event_type="INITIAL_PURCHASE",
        app_user_id=buyer_id,
        product_id="onflow_pro_monthly",
        subscriber_attributes={"onflow_user_id": {"value": victim_id}},
    )

    assert result["user_id"] == buyer_id
    assert client.app.state.db.get_user_tier(buyer_id) == "pro"
    assert client.app.state.db.get_user_tier(victim_id) != "pro"


def test_older_expiration_cannot_overwrite_newer_renewal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    user_id = _create_user(client, "rc-stale-expiration@onflow.test")

    renewed = _post_event(
        client,
        event_id="evt-renew-newer",
        event_type="RENEWAL",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=2_000,
    )
    stale = _post_event(
        client,
        event_id="evt-expire-older",
        event_type="EXPIRATION",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=1_000,
    )

    assert renewed["action"] == "tier_set_pro"
    assert stale["action"] == "stale_event_ignored"
    assert client.app.state.db.get_user_tier(user_id) == "pro"

    duplicate = _post_event(
        client,
        event_id="evt-expire-older",
        event_type="EXPIRATION",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=1_000,
    )
    assert duplicate["action"] == "duplicate_event_ignored"


def test_same_timestamp_expiration_does_not_overwrite_pro(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    user_id = _create_user(client, "rc-timestamp-tie@onflow.test")

    _post_event(
        client,
        event_id="evt-tie-renewal",
        event_type="RENEWAL",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=5_000,
    )
    tied_expiration = _post_event(
        client,
        event_id="evt-tie-expiration",
        event_type="EXPIRATION",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=5_000,
    )

    assert tied_expiration["action"] == "stale_event_ignored"
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_newer_expiration_downgrades_pro(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    user_id = _create_user(client, "rc-new-expiration@onflow.test")

    _post_event(
        client,
        event_id="evt-old-renewal",
        event_type="RENEWAL",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=1_000,
    )
    expired = _post_event(
        client,
        event_id="evt-new-expiration",
        event_type="EXPIRATION",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=2_000,
    )

    assert expired["action"] == "tier_set_free"
    assert client.app.state.db.get_user_tier(user_id) == "free"


def test_expiring_one_product_keeps_other_pro_product_active(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch)
    user_id = _create_user(client, "rc-overlapping-products@onflow.test")

    _post_event(
        client,
        event_id="evt-monthly-active",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=1_000,
    )
    _post_event(
        client,
        event_id="evt-annual-active",
        event_type="INITIAL_PURCHASE",
        app_user_id=user_id,
        product_id="onflow_pro_annual",
        event_timestamp_ms=2_000,
    )
    monthly_expired = _post_event(
        client,
        event_id="evt-monthly-expired",
        event_type="EXPIRATION",
        app_user_id=user_id,
        product_id="onflow_pro_monthly",
        event_timestamp_ms=3_000,
    )

    assert monthly_expired["action"] == "entitlement_remains_pro"
    assert client.app.state.db.get_user_tier(user_id) == "pro"

    annual_expired = _post_event(
        client,
        event_id="evt-annual-expired",
        event_type="EXPIRATION",
        app_user_id=user_id,
        product_id="onflow_pro_annual",
        event_timestamp_ms=4_000,
    )
    assert annual_expired["action"] == "tier_set_free"
    assert client.app.state.db.get_user_tier(user_id) == "free"


def test_unrelated_product_expiration_cannot_revoke_pro(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_pro_products(monkeypatch, "onflow_pro_monthly")
    user_id = _create_user(client, "rc-unrelated-expiration@onflow.test")
    client.app.state.db.set_user_tier(user_id, "pro")

    ignored = _post_event(
        client,
        event_id="evt-unrelated-expiration",
        event_type="EXPIRATION",
        app_user_id=user_id,
        product_id="some_other_app_product",
        event_timestamp_ms=9_000,
    )

    assert ignored["action"] == "ignored_unknown_product"
    assert client.app.state.db.get_user_tier(user_id) == "pro"
