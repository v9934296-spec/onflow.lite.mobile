"""Pure tier feature-gating helpers."""

from __future__ import annotations

_FEATURES_BY_TIER: dict[str, set[str]] = {
    "trial": {"record_session", "upload_clip", "pte", "battles", "stats", "feed"},
    "free": {"record_session", "upload_clip", "pte", "battles", "stats", "feed"},
    "free_expired": {"feed"},
    "pro": {"record_session", "upload_clip", "pte", "battles", "stats", "feed"},
    "session_reup": {"record_session", "upload_clip", "pte", "battles", "stats", "feed"},
}


def tier_has_feature(tier: str, feature: str) -> bool:
    normalized_tier = (tier or "").strip().lower()
    normalized_feature = (feature or "").strip().lower()
    return normalized_feature in _FEATURES_BY_TIER.get(normalized_tier, set())
