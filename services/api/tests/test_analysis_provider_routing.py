"""Tier → analysis provider routing (Gemini free, Pegasus pro, rollback flag)."""

from __future__ import annotations

from app.core.config import Settings
from app.core.tiers import (
    normalized_review_model_for_provider,
    resolve_analysis_provider_for_tier,
)


def _settings(**kwargs: object) -> Settings:
    base = dict(
        gemini_api_key="g",
        twelvelabs_api_key="t",
        force_gemini_for_pro=False,
    )
    base.update(kwargs)
    return Settings(**base)


def test_free_tier_uses_gemini() -> None:
    s = _settings()
    assert resolve_analysis_provider_for_tier("free", s) == "gemini"
    assert normalized_review_model_for_provider("gemini") == "gemini"


def test_pro_tier_uses_twelvelabs() -> None:
    s = _settings()
    assert resolve_analysis_provider_for_tier("pro", s) == "twelvelabs"
    assert normalized_review_model_for_provider("twelvelabs") == "pegasus"


def test_legacy_coach_normalizes_to_pro_provider() -> None:
    s = _settings()
    assert resolve_analysis_provider_for_tier("coach", s) == "twelvelabs"


def test_force_gemini_for_pro_rollback() -> None:
    s = _settings(force_gemini_for_pro=True)
    assert resolve_analysis_provider_for_tier("pro", s) == "gemini"
    assert resolve_analysis_provider_for_tier("coach", s) == "gemini"
