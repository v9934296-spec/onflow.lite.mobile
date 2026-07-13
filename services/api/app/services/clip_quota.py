"""Clip submission quota: Pro unlimited → bonus pool → monthly free cap."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.core.tiers import normalize_tier, tier_has_unlimited_analyses
from app.repositories.clip_jobs import ClipJobRepository
from app.repositories.identity import IdentityRepository


def reserve_clip_submission(request: Request, user_id: str) -> tuple[str, str | None]:
    """
    Decide how this submission is charged. Returns (tier_for_job, quota_source).
    quota_source: 'unlimited' | 'bonus' | 'monthly' | None (should not happen).

    Order: unlimited tier → monthly free cap → OAuth signup bonus pool → purchased bonus pool.
    """
    settings = get_settings()
    db: IdentityRepository = request.app.state.db
    repo: ClipJobRepository = request.app.state.repo

    tier = normalize_tier(db.get_user_tier(user_id))
    if tier_has_unlimited_analyses(tier):
        return tier, "unlimited"

    cap = max(1, settings.rate_limit_free)
    used = repo.count_monthly_free_jobs(user_id)
    if used < cap:
        return tier, "monthly"

    if db.try_consume_one_bonus(user_id):
        return tier, "bonus"

    raise HTTPException(
        status_code=429,
        detail="Monthly free analysis limit reached. Upgrade, purchase a Re-Up Pack, or wait until next month.",
    )
