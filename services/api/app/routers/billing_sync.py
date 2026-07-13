"""Client-initiated billing sync — links the RevenueCat customer id and reads entitlement state.

Entitlement *changes* (tier upgrades/downgrades, Re-Up bonus credits) are applied ONLY by
the authenticated RevenueCat webhook (`/api/v1/webhooks/revenuecat`), which is the single
source of truth. This endpoint deliberately does NOT grant tier or bonus from client-supplied
claims: there is no server-side RevenueCat verification key, so trusting the client would let
any signed-in user self-upgrade to a paid tier (unlimited analyses) for free.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, get_user_tier_for_beta
from app.core.tiers import normalize_tier, tier_has_unlimited_analyses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class SyncRequest(BaseModel):
    """Client's view of entitlements after purchase or restore.

    ``has_pro``, ``sync_tier`` and ``bonus_purchased`` are accepted for backward
    compatibility but are **informational only** — the server never grants tier or
    bonus from these client claims. The RevenueCat webhook is the source of truth.
    """

    has_pro: bool = Field(
        description="RevenueCat SDK's view of the 'pro' entitlement. Informational only — ignored."
    )
    sync_tier: str | None = Field(
        default=None,
        description="Client-reported tier. Informational only — ignored; the webhook sets tier.",
    )
    bonus_purchased: int = Field(
        default=0,
        description="Client-reported Re-Up bonus count. Informational only — ignored; "
        "the webhook credits Re-Up packs.",
    )
    rc_app_user_id: str | None = Field(
        default=None,
        description="RevenueCat app_user_id so the backend can link for future webhooks.",
    )


class SyncResponse(BaseModel):
    tier: str
    bonus_analyses: int
    monthly_free_remaining: int | None


@router.post("/sync", response_model=SyncResponse)
def sync_billing(
    request: Request,
    body: SyncRequest,
    user_id: str = Depends(get_current_user),
) -> SyncResponse:
    """
    Link the caller's RevenueCat customer id and return current entitlement state.

    This does NOT change entitlements. Tier changes (purchase, renewal, expiration,
    cancellation) and Re-Up bonus credits are applied exclusively by the authenticated
    RevenueCat webhook, which is the single source of truth. After a purchase the client
    should call this to link its RC id, then refetch entitlement state once the webhook
    lands (typically within seconds).
    """
    db = request.app.state.db
    repo = request.app.state.repo
    settings = request.app.state.settings

    current_tier = normalize_tier(get_user_tier_for_beta(user_id, db.get_user_tier(user_id)))

    # Linking the RC customer id is safe — it does not change the tier (we write the
    # already-current tier) and lets future webhooks resolve this user. Only link when
    # the RC id is unclaimed or already belongs to this user.
    if body.rc_app_user_id and body.rc_app_user_id.strip():
        rc_id = body.rc_app_user_id.strip()
        existing = db.get_user_by_rc_customer(rc_id)
        if existing is None or existing == user_id:
            db.set_user_tier(user_id, current_tier, rc_customer_id=rc_id)
            logger.info("billing_sync linked rc_id user_id=%s", user_id)

    bonus = db.get_bonus_analyses(user_id)
    if tier_has_unlimited_analyses(current_tier):
        return SyncResponse(
            tier=current_tier,
            bonus_analyses=bonus,
            monthly_free_remaining=None,
        )

    cap = max(1, settings.rate_limit_free)
    used = repo.count_monthly_free_jobs(user_id)
    remaining = max(0, cap - used)
    return SyncResponse(
        tier=current_tier,
        bonus_analyses=bonus,
        monthly_free_remaining=remaining,
    )
