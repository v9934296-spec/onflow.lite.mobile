"""
Lock subscription lifecycle behavior:

1. RevenueCat CANCELLATION / PRODUCT_CHANGE / BILLING_ISSUE must NOT downgrade —
   the user is still entitled to Pro when those events fire. Only EXPIRATION
   revokes the tier.
2. Trial expiry is applied lazily at tier read time (no scheduler): an expired
   trial downgrades to free_expired on the next get_user_tier call and writes a
   trial_expired subscription audit event. A trial row with no expiry timestamp
   downgrades immediately (fail toward the paid funnel, never toward unlimited).
3. free_expired users cannot upload clips or start sessions; feed remains readable.

Uses the shared ``client`` fixture from tests/conftest.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_UPLOAD_BODY = {
    "duration_seconds": 4.5,
    "width_px": 1080,
    "height_px": 1920,
    "content_type": "video/mp4",
    "size_bytes": 1024,
}


def _create_user(client: TestClient, email: str) -> str:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()["user_id"]


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def _set_tier(client: TestClient, user_id: str, tier: str) -> None:
    client.app.state.db.set_user_tier(user_id, tier)


def _webhook(client: TestClient, event_type: str, user_id: str, product_id: str) -> dict:
    r = client.post(
        "/api/v1/webhooks/revenuecat",
        json={
            "event": {
                "type": event_type,
                "app_user_id": user_id,
                "product_id": product_id,
                "id": f"evt-{event_type}-{user_id}",
            }
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Webhook: entitled-lifecycle events must not revoke Pro
# ---------------------------------------------------------------------------


def test_cancellation_does_not_downgrade_pro(client: TestClient) -> None:
    """User cancels auto-renew mid-period: they keep Pro until EXPIRATION."""
    user_id = _create_user(client, "cancel-keeps-pro@onflow.test")
    _set_tier(client, user_id, "pro")

    body = _webhook(client, "CANCELLATION", user_id, "onflow_pro_monthly")

    assert body["action"] != "tier_set_free"
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_product_change_does_not_downgrade_pro(client: TestClient) -> None:
    """Switching products (e.g. monthly -> annual) keeps the subscription active."""
    user_id = _create_user(client, "product-change-keeps-pro@onflow.test")
    _set_tier(client, user_id, "pro")

    body = _webhook(client, "PRODUCT_CHANGE", user_id, "onflow_pro_annual")

    assert body["action"] != "tier_set_free"
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_billing_issue_does_not_downgrade_pro(client: TestClient) -> None:
    """Billing retry / grace period may recover; EXPIRATION handles true loss."""
    user_id = _create_user(client, "billing-issue-keeps-pro@onflow.test")
    _set_tier(client, user_id, "pro")

    body = _webhook(client, "BILLING_ISSUE", user_id, "onflow_pro_monthly")

    assert body["action"] != "tier_set_free"
    assert client.app.state.db.get_user_tier(user_id) == "pro"


def test_expiration_downgrades_pro_to_free(client: TestClient) -> None:
    """EXPIRATION is the one event that revokes the tier."""
    user_id = _create_user(client, "expiration-downgrades@onflow.test")
    _set_tier(client, user_id, "pro")

    body = _webhook(client, "EXPIRATION", user_id, "onflow_pro_monthly")

    assert body["action"] == "tier_set_free"
    assert client.app.state.db.get_user_tier(user_id) == "free"


def test_initial_purchase_still_grants_pro(client: TestClient) -> None:
    """Regression guard: the upgrade path is unchanged by the downgrade fix."""
    user_id = _create_user(client, "purchase-grants-pro@onflow.test")

    body = _webhook(client, "INITIAL_PURCHASE", user_id, "onflow_pro_monthly")

    assert body["action"] == "tier_set_pro"
    assert client.app.state.db.get_user_tier(user_id) == "pro"


# ---------------------------------------------------------------------------
# Trial: lazy expiry at tier read time
# ---------------------------------------------------------------------------


def _load_user_row(client: TestClient, user_id: str):
    from app.core.database import get_engine
    from app.models import UserModel

    with Session(get_engine()) as session:
        return session.get(UserModel, user_id)


def _force_trial_expiry(client: TestClient, user_id: str, expires_at: datetime | None) -> None:
    from app.core.database import get_engine
    from app.models import UserModel

    with Session(get_engine()) as session:
        row = session.get(UserModel, user_id)
        assert row is not None
        row.tier = "trial"
        row.trial_started_at = datetime.now(timezone.utc) - timedelta(days=8)
        row.trial_expires_at = expires_at
        session.add(row)
        session.commit()


def test_active_trial_is_not_downgraded(client: TestClient) -> None:
    user_id = _create_user(client, "trial-active@onflow.test")
    _force_trial_expiry(
        client, user_id, datetime.now(timezone.utc) + timedelta(days=3)
    )

    assert client.app.state.db.get_user_tier(user_id) == "trial"


def test_expired_trial_downgrades_on_tier_read(client: TestClient) -> None:
    user_id = _create_user(client, "trial-expired@onflow.test")
    _force_trial_expiry(
        client, user_id, datetime.now(timezone.utc) - timedelta(hours=1)
    )

    assert client.app.state.db.get_user_tier(user_id) == "free_expired"

    row = _load_user_row(client, user_id)
    assert row is not None
    assert row.tier == "free_expired"
    assert row.subscription_status == "expired"


def test_trial_without_expiry_window_downgrades_immediately(client: TestClient) -> None:
    """A trial row with no window (model-default tier) must not mean unlimited."""
    user_id = _create_user(client, "trial-no-window@onflow.test")
    _force_trial_expiry(client, user_id, None)

    assert client.app.state.db.get_user_tier(user_id) == "free_expired"


def test_expired_trial_writes_audit_event(client: TestClient) -> None:
    from app.core.database import get_engine
    from app.models import SubscriptionEventModel

    user_id = _create_user(client, "trial-audit@onflow.test")
    _force_trial_expiry(
        client, user_id, datetime.now(timezone.utc) - timedelta(hours=1)
    )

    client.app.state.db.get_user_tier(user_id)

    with Session(get_engine()) as session:
        events = list(
            session.exec(
                select(SubscriptionEventModel).where(
                    SubscriptionEventModel.user_id == user_id,
                    SubscriptionEventModel.event_type == "trial_expired",
                )
            )
        )
    assert len(events) == 1
    assert events[0].from_tier == "trial"
    assert events[0].to_tier == "free_expired"


def test_expired_trial_no_longer_has_unlimited_quota(client: TestClient) -> None:
    """The product consequence: an expired trial hits the monthly free cap logic."""
    from app.core.tiers import tier_has_unlimited_analyses

    user_id = _create_user(client, "trial-quota@onflow.test")
    _force_trial_expiry(
        client, user_id, datetime.now(timezone.utc) - timedelta(hours=1)
    )

    tier = client.app.state.db.get_user_tier(user_id)
    assert not tier_has_unlimited_analyses(tier)


# ---------------------------------------------------------------------------
# free_expired feature lockout on upload + session creation
# ---------------------------------------------------------------------------


def test_free_expired_cannot_initiate_upload(client: TestClient) -> None:
    email = "free-expired-upload@onflow.test"
    user_id = _create_user(client, email)
    _set_tier(client, user_id, "free_expired")
    headers = _auth_headers(client, email)

    r = client.post("/api/v1/clips/initiate-upload", json=_UPLOAD_BODY, headers=headers)

    assert r.status_code == 403
    assert "free trial has ended" in r.json()["detail"].lower()


def test_free_expired_cannot_create_session(client: TestClient) -> None:
    email = "free-expired-session@onflow.test"
    user_id = _create_user(client, email)
    _set_tier(client, user_id, "free_expired")
    headers = _auth_headers(client, email)

    r = client.post("/api/v1/sessions", json={"spot_label": "Park"}, headers=headers)

    assert r.status_code == 403
    assert "free trial has ended" in r.json()["detail"].lower()


def test_free_user_can_upload_and_create_session(client: TestClient) -> None:
    email = "free-user-works@onflow.test"
    user_id = _create_user(client, email)
    _set_tier(client, user_id, "free")
    headers = _auth_headers(client, email)

    upload = client.post("/api/v1/clips/initiate-upload", json=_UPLOAD_BODY, headers=headers)
    assert upload.status_code == 201, upload.text

    session = client.post("/api/v1/sessions", json={"spot_label": "Park"}, headers=headers)
    assert session.status_code == 201, session.text
