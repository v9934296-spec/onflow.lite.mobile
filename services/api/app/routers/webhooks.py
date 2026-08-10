"""RevenueCat webhook — subscription tier + Re-Up Pack bonus credits."""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.core.rate_limit import limiter, remote_ip_key, webhook_limit_per_minute
from app.services.beta_observability import log_beta
from app.services.revenuecat_events import (
    apply_revenuecat_mutation,
    record_revenuecat_noop,
)

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

# Downgrade product state ONLY on EXPIRATION — the event RevenueCat fires when
# access for that product has actually ended. The transaction service derives the
# user's tier from all currently-active configured Pro products.
_FREE_EVENTS = frozenset({"EXPIRATION"})

# Lifecycle events we acknowledge and log but take no entitlement action on.
_ACKNOWLEDGED_LIFECYCLE_EVENTS = frozenset(
    {
        "CANCELLATION",
        "PRODUCT_CHANGE",
        "BILLING_ISSUE",
        "SUBSCRIBER_ALIAS",
    }
)


def _event_int(event: dict, name: str) -> int | None:
    raw = event.get(name)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _identity_candidates(event: dict, rc_app_user_id: str) -> list[str]:
    """Return RevenueCat-controlled identities that may map to the account.

    Do not trust a client-set subscriber attribute as an account selector. The SDK
    identifies users with ``app_user_id`` and RevenueCat supplies the original id
    and aliases needed to resolve anonymous-to-identified transitions.
    """
    original = str(event.get("original_app_user_id") or "").strip()
    aliases = event.get("aliases")

    out: list[str] = []
    for value in (rc_app_user_id, original):
        if value and value not in out:
            out.append(value)
    if isinstance(aliases, list):
        for raw in aliases:
            value = str(raw or "").strip()
            if value and value not in out:
                out.append(value)
    return out


def _verify_webhook_auth(request: Request) -> None:
    settings = get_settings()
    secret = (settings.rc_webhook_secret or "").strip()
    if settings.is_production_or_staging:
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
    if not hmac.compare_digest(auth_header, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="Invalid webhook authorization.")


def _reup_product_ids(settings) -> set[str]:
    out: set[str] = {settings.rc_product_reup_pack.strip()}
    for x in (settings.rc_legacy_bonus_product_ids or "").split(","):
        value = x.strip()
        if value:
            out.add(value)
    out.discard("")
    return out


def _pro_product_ids(settings) -> set[str]:
    return {
        value.strip()
        for value in (settings.rc_pro_product_ids or "").split(",")
        if value.strip()
    }


def _duplicate_response(event_id: str) -> dict:
    return {"ok": True, "action": "duplicate_event_ignored", "event_id": event_id}


def _raise_unknown_user_retry(event_type: str, rc_app_user_id: str) -> None:
    logger.warning(
        "RevenueCat paid event could not resolve user; requesting retry type=%s app_user_id=%s",
        event_type,
        rc_app_user_id,
    )
    raise HTTPException(
        status_code=503,
        detail="RevenueCat user is not linked yet; retry this webhook.",
    )


def _raise_transfer_reconciliation_required(event: dict) -> None:
    """Fail closed until the backend can fetch authoritative subscriber state.

    TRANSFER events move all entitlements between users and do not carry the
    normal per-product fields required by the event-state reducer below. Returning
    2xx would silently leave one or both accounts with incorrect paid access.
    """
    logger.error(
        "RevenueCat TRANSFER requires authoritative reconciliation transferred_from=%s transferred_to=%s",
        event.get("transferred_from"),
        event.get("transferred_to"),
    )
    raise HTTPException(
        status_code=503,
        detail=(
            "RevenueCat transfer requires authoritative subscriber reconciliation; "
            "retry this webhook after reconciliation is configured."
        ),
    )


@router.post("/revenuecat")
@limiter.limit(webhook_limit_per_minute, key_func=remote_ip_key)
async def revenuecat_webhook(request: Request) -> dict:
    """Apply authenticated RevenueCat subscription and Re-Up events."""
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
    event_timestamp_ms = _event_int(event, "event_timestamp_ms")

    if not event_type:
        return {"ok": True, "action": "ignored_missing_fields"}
    if not event_id:
        logger.warning(
            "RevenueCat webhook missing event.id — acknowledging without mutate type=%s",
            event_type,
        )
        return {"ok": True, "action": "ignored_missing_event_id"}
    if event_type == "TRANSFER":
        _raise_transfer_reconciliation_required(event)
    if not rc_app_user_id:
        return {"ok": True, "action": "ignored_missing_fields"}

    if event_type == "INITIAL_PURCHASE":
        logger.info(
            "[PAID] First-time purchase: product_id=%s app_user_id=%s",
            product_id,
            rc_app_user_id,
        )

    candidate_user_ids = _identity_candidates(event, rc_app_user_id)
    settings = get_settings()
    reup_ids = _reup_product_ids(settings)
    pro_ids = _pro_product_ids(settings)

    if not pro_ids and settings.is_production_or_staging:
        logger.error("RevenueCat Pro product allowlist is empty in a deployed environment")
        raise HTTPException(
            status_code=503,
            detail="RevenueCat Pro products are not configured; retry this webhook.",
        )

    # Development compatibility: local lifecycle tests can exercise expiration
    # without reproducing every deployed environment variable.
    if not pro_ids and product_id:
        pro_ids = {product_id}

    if event_type in _PRO_EVENTS and product_id in reup_ids:
        applied = apply_revenuecat_mutation(
            event_id=event_id,
            candidate_user_ids=candidate_user_ids,
            rc_customer_id=rc_app_user_id,
            bonus_delta=10,
        )
        if applied.duplicate:
            return _duplicate_response(event_id)
        if applied.user_id is None:
            _raise_unknown_user_retry(event_type, rc_app_user_id)

        total = int(applied.bonus_total or 0)
        log_beta(
            "beta_reup_pack_credited",
            user_id=applied.user_id,
            product_id=product_id,
            bonus_total=total,
        )
        logger.info(
            "reup_bonus user_id=%s product_id=%s bonus_total=%s",
            applied.user_id,
            product_id,
            total,
        )
        return {
            "ok": True,
            "action": "reup_bonus_added",
            "user_id": applied.user_id,
            "bonus_analyses": total,
        }

    entitlement_active: bool | None = None
    if event_type in _PRO_EVENTS:
        if product_id not in pro_ids:
            # Leave the event id unclaimed so an operator can correct the allowlist
            # and replay the original event from RevenueCat.
            return {
                "ok": True,
                "action": "ignored_unknown_product",
                "product_id": product_id,
            }
        entitlement_active = True
    elif event_type in _FREE_EVENTS:
        if product_id not in pro_ids:
            # Leave the event replayable too: this may be a truly unrelated product,
            # or it may expose a temporarily incomplete allowlist. Either way it
            # cannot affect OnFlow until explicitly configured as a Pro product.
            return {
                "ok": True,
                "action": "ignored_unknown_product",
                "product_id": product_id,
            }
        entitlement_active = False

    if entitlement_active is not None:
        applied = apply_revenuecat_mutation(
            event_id=event_id,
            candidate_user_ids=candidate_user_ids,
            rc_customer_id=rc_app_user_id,
            entitlement_product_id=product_id,
            entitlement_active=entitlement_active,
            pro_product_ids=pro_ids,
            event_timestamp_ms=event_timestamp_ms,
        )
        if applied.duplicate:
            return _duplicate_response(event_id)
        if applied.user_id is None:
            _raise_unknown_user_retry(event_type, rc_app_user_id)
        if applied.stale:
            logger.info(
                "stale_revenuecat_event_ignored user_id=%s event=%s product_id=%s event_id=%s timestamp_ms=%s",
                applied.user_id,
                event_type,
                product_id,
                event_id,
                event_timestamp_ms,
            )
            return {
                "ok": True,
                "action": "stale_event_ignored",
                "user_id": applied.user_id,
                "event_id": event_id,
            }

        resulting_tier = applied.tier or "free"
        log_beta(
            "beta_tier_changed",
            user_id=applied.user_id,
            new_tier=resulting_tier,
            event_type=event_type,
        )
        logger.info(
            "tier_changed user_id=%s tier=%s event=%s product_id=%s",
            applied.user_id,
            resulting_tier,
            event_type,
            product_id,
        )
        action = (
            "entitlement_remains_pro"
            if event_type == "EXPIRATION" and resulting_tier == "pro"
            else f"tier_set_{resulting_tier}"
        )
        return {
            "ok": True,
            "action": action,
            "user_id": applied.user_id,
        }

    if not record_revenuecat_noop(event_id):
        return _duplicate_response(event_id)

    if event_type in _ACKNOWLEDGED_LIFECYCLE_EVENTS:
        logger.info(
            "lifecycle_event_acknowledged user_id=%s event=%s product_id=%s (no tier change)",
            rc_app_user_id,
            event_type,
            product_id,
        )
        return {"ok": True, "action": "lifecycle_acknowledged", "event_type": event_type}

    return {"ok": True, "action": "ignored_event_type", "event_type": event_type}
