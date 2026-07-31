"""RevenueCat webhook — subscription tier + Re-Up Pack bonus credits."""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.core.rate_limit import limiter, remote_ip_key, webhook_limit_per_minute
from app.services.beta_observability import log_beta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

_PRO_EVENTS = frozenset(
    {
        "INITIAL_PURCHASE",
        "RENEWAL",
        "UNCANCELLATION",
        "NON_RENEWING_PURCHASE",
    }
)

# Downgrade ONLY on EXPIRATION — the event RevenueCat fires when entitlement
# access has actually ended.
#
# Deliberately NOT downgrade events (the user is still entitled when they fire):
# - CANCELLATION: auto-renew was turned off, but the user keeps Pro until the
#   end of the period they already paid for. RevenueCat sends EXPIRATION when
#   access truly ends; downgrading here would revoke paid time.
# - PRODUCT_CHANGE: the subscription is still active; the user switched
#   products (e.g. monthly → annual). Tier stays pro.
# - BILLING_ISSUE: Apple's grace period / billing retry may still recover the
#   charge. If it doesn't, EXPIRATION follows and we downgrade then.
_FREE_EVENTS = frozenset({"EXPIRATION"})

# Lifecycle events we acknowledge and log but take no tier action on. Listed
# explicitly so a future reader knows they were considered, not missed.
_ACKNOWLEDGED_LIFECYCLE_EVENTS = frozenset(
    {
        "CANCELLATION",
        "PRODUCT_CHANGE",
        "BILLING_ISSUE",
        "SUBSCRIBER_ALIAS",
        "TRANSFER",
    }
)


def _subscriber_attr_value(attrs: object, name: str) -> str | None:
    if not isinstance(attrs, dict):
        return None
    raw = attrs.get(name)
    if isinstance(raw, dict):
        v = raw.get("value")
        return str(v).strip() if v is not None and str(v).strip() else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _verify_webhook_auth(request: Request) -> None:
    settings = get_settings()
    secret = (settings.rc_webhook_secret or "").strip()
    if settings.is_production:
        if not secret:
            raise HTTPException(
                status_code=401,
                detail="Webhook authorization is not configured.",
            )
    elif not secret:
        logger.warning(
            "ONFLOW_RC_WEBHOOK_SECRET not set — accepting webhook without auth (development only)"
        )
        return
    auth_header = request.headers.get("authorization", "")
    # Constant-time comparison so the static secret can't be probed via timing.
    if not hmac.compare_digest(auth_header, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Invalid webhook authorization.")


def _reup_product_ids(settings) -> set[str]:
    out: set[str] = {settings.rc_product_reup_pack.strip()}
    for x in (settings.rc_legacy_bonus_product_ids or "").split(","):
        t = x.strip()
        if t:
            out.add(t)
    out.discard("")
    return out


def _pro_product_ids(settings) -> set[str]:
    out: set[str] = set()
    for x in (settings.rc_pro_product_ids or "").split(","):
        t = x.strip()
        if t:
            out.add(t)
    return out


def _tier_for_subscription_product(product_id: str, settings) -> str | None:
    """Return 'pro' only for allowlisted Store product IDs; otherwise None (no tier change)."""
    pid = (product_id or "").strip()
    if not pid:
        return None
    allowed = _pro_product_ids(settings)
    if not allowed:
        logger.warning(
            "ONFLOW_RC_PRO_PRODUCT_IDS is empty — ignoring subscription product_id=%s",
            pid,
        )
        return None
    if pid in allowed:
        return "pro"
    logger.info("ignoring non-allowlisted product_id=%s for tier grant", pid)
    return None


@router.post("/revenuecat")
@limiter.limit(webhook_limit_per_minute, key_func=remote_ip_key)
async def revenuecat_webhook(request: Request) -> dict:
    """
    RevenueCat sends events here when subscriptions or one-time purchases change.
    Updates the user tier for subscriptions; Re-Up Pack adds bonus analyses (stackable).

    Tier is granted on purchase/renewal events and revoked ONLY on EXPIRATION —
    cancellation and billing-retry events leave the user's remaining paid access
    intact (see _FREE_EVENTS comment above).
    """
    _verify_webhook_auth(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON.") from None

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    event = body.get("event")
    if not isinstance(event, dict):
        event = {}

    event_type = str(event.get("type") or "").strip()
    rc_app_user_id = str(event.get("app_user_id") or "").strip()
    product_id = str(event.get("product_id") or "").strip()
    event_id = str(event.get("id") or "").strip()

    if not event_type or not rc_app_user_id:
        return {"ok": True, "action": "ignored_missing_fields"}

    if not event_id:
        logger.warning(
            "RevenueCat webhook missing event.id — acknowledging without mutate type=%s",
            event_type,
        )
        return {"ok": True, "action": "ignored_missing_event_id"}

    if event_type == "INITIAL_PURCHASE":
        logger.info(
            "[PAID] First-time purchase: product_id=%s app_user_id=%s",
            product_id,
            rc_app_user_id,
        )

    db = request.app.state.db
    if not db.try_record_rc_webhook_event(event_id):
        return {"ok": True, "action": "duplicate_event_ignored", "event_id": event_id}

    user_id = rc_app_user_id
    if not db.user_exists(user_id):
        attrs = event.get("subscriber_attributes")
        onflow_uid = _subscriber_attr_value(attrs, "onflow_user_id")
        if onflow_uid and db.user_exists(onflow_uid):
            user_id = onflow_uid

    settings = get_settings()
    reup_ids = _reup_product_ids(settings)

    if event_type in _PRO_EVENTS and product_id in reup_ids:
        if not db.user_exists(user_id):
            return {"ok": True, "action": "ignored_unknown_user_reup", "user_id": user_id}
        total = db.add_bonus_analyses(user_id, 3)
        log_beta(
            "beta_reup_pack_credited",
            user_id=user_id,
            product_id=product_id,
            bonus_total=total,
        )
        logger.info(
            "reup_bonus user_id=%s product_id=%s bonus_total=%s",
            user_id,
            product_id,
            total,
        )
        return {"ok": True, "action": "reup_bonus_added", "user_id": user_id, "bonus_analyses": total}

    new_tier: str | None = None
    if event_type in _PRO_EVENTS:
        new_tier = _tier_for_subscription_product(product_id, settings)
        if new_tier is None:
            return {
                "ok": True,
                "action": "ignored_unknown_product",
                "product_id": product_id,
            }
    elif event_type in _FREE_EVENTS:
        new_tier = "free"

    if new_tier:
        db.set_user_tier(user_id, new_tier, rc_customer_id=rc_app_user_id)
        log_beta(
            "beta_tier_changed",
            user_id=user_id,
            new_tier=new_tier,
            event_type=event_type,
        )
        logger.info(
            "tier_changed user_id=%s tier=%s event=%s product_id=%s",
            user_id,
            new_tier,
            event_type,
            product_id,
        )
        return {"ok": True, "action": f"tier_set_{new_tier}", "user_id": user_id}

    if event_type in _ACKNOWLEDGED_LIFECYCLE_EVENTS:
        logger.info(
            "lifecycle_event_acknowledged user_id=%s event=%s product_id=%s (no tier change)",
            user_id,
            event_type,
            product_id,
        )
        return {"ok": True, "action": "lifecycle_acknowledged", "event_type": event_type}

    return {"ok": True, "action": "ignored_event_type", "event_type": event_type}
