"""Subscription tier helpers — `users.tier`, clip quota, and analysis provider routing."""

from __future__ import annotations

from typing import Literal

from app.core.config import Settings

AnalysisProvider = Literal["gemini", "twelvelabs"]


def normalize_tier(raw: str | None) -> str:
    t = (raw or "free").strip().lower()
    if t == "coach":
        return "pro"
    if t in ("trial", "free", "free_expired", "pro", "session_reup"):
        return t
    return "free"


def tier_has_unlimited_analyses(tier: str) -> bool:
    """Only an active trial skips the monthly product cap. Pro is capped (see rate_limit_pro)."""
    return normalize_tier(tier) == "trial"


def monthly_analysis_cap(tier: str | None, settings: Settings) -> int | None:
    """
    Calendar-month product analysis cap for the tier.

    Returns ``None`` when analyses are unlimited (active trial only).
    """
    t = normalize_tier(tier)
    if tier_has_unlimited_analyses(t):
        return None
    if t in {"pro", "session_reup"}:
        return max(1, int(settings.rate_limit_pro))
    if t == "free_expired":
        return 0
    return max(1, int(settings.rate_limit_free))


def resolve_gemini_model_for_tier(tier: str | None, settings: Settings) -> str:
    """
    Single source of truth for which Gemini model to run for a user's tier.

    - pro → ``settings.gemini_model_pro`` (paid tier)
    - free and any other normalized tier → ``settings.gemini_model_free``

    If a tier-specific field is empty, ``settings.gemini_model`` is used as a legacy
    single-model override (``ONFLOW_GEMINI_MODEL``), then the other tier field as a
    last resort for paid.
    """
    t = normalize_tier(tier)
    legacy = (settings.gemini_model or "").strip()
    if t == "pro":
        m = (settings.gemini_model_pro or "").strip()
        if m:
            return m
        if legacy:
            return legacy
        return (settings.gemini_model_free or "").strip()
    m = (settings.gemini_model_free or "").strip()
    if m:
        return m
    return legacy


def resolve_analysis_provider_for_tier(
    tier: str | None,
    settings: Settings,
) -> AnalysisProvider:
    """Pro → Twelve Labs Pegasus unless rollback flag forces Gemini."""
    if settings.force_gemini_for_pro:
        return "gemini"
    if normalize_tier(tier) == "pro":
        return "twelvelabs"
    return "gemini"


def normalized_review_model_for_provider(provider: AnalysisProvider) -> str:
    return "pegasus" if provider == "twelvelabs" else "gemini"
