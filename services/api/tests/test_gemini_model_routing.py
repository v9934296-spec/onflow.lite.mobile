"""Unit tests for tier → Gemini model resolution (honesty-first routing, no stub reviews)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.tiers import normalize_tier, resolve_gemini_model_for_tier


def test_free_tier_resolves_to_flash_lite_default() -> None:
    s = Settings(
        gemini_api_key="x",
        gemini_model_free="gemini-2.5-flash-lite",
        gemini_model_pro="gemini-2.5-flash",
        gemini_model="gemini-2.5-flash",
    )
    assert resolve_gemini_model_for_tier("free", s) == "gemini-2.5-flash-lite"


def test_pro_tier_resolves_to_flash_default() -> None:
    s = Settings(
        gemini_api_key="x",
        gemini_model_free="gemini-2.5-flash-lite",
        gemini_model_pro="gemini-2.5-flash",
        gemini_model="gemini-2.5-flash",
    )
    assert resolve_gemini_model_for_tier("pro", s) == "gemini-2.5-flash"


def test_legacy_coach_tier_normalizes_to_pro_model() -> None:
    s = Settings(
        gemini_api_key="x",
        gemini_model_free="gemini-2.5-flash-lite",
        gemini_model_pro="gemini-2.5-flash",
    )
    assert normalize_tier("coach") == "pro"
    assert resolve_gemini_model_for_tier("coach", s) == resolve_gemini_model_for_tier(
        "pro", s
    )


def test_unknown_tier_normalizes_to_free_model() -> None:
    s = Settings(
        gemini_api_key="x",
        gemini_model_free="gemini-2.5-flash-lite",
        gemini_model_pro="gemini-2.5-flash",
    )
    assert normalize_tier("not-a-real-tier") == "free"
    assert resolve_gemini_model_for_tier("not-a-real-tier", s) == s.gemini_model_free


@pytest.mark.parametrize(
    "env_key, env_val, tier, expected",
    [
        ("ONFLOW_GEMINI_MODEL_FREE", "custom-lite", "free", "custom-lite"),
        ("ONFLOW_GEMINI_MODEL_PRO", "custom-flash", "pro", "custom-flash"),
        ("ONFLOW_GEMINI_MODEL_PRO", "custom-flash", "coach", "custom-flash"),
    ],
)
def test_env_overrides_honored(
    monkeypatch: pytest.MonkeyPatch,
    env_key: str,
    env_val: str,
    tier: str,
    expected: str,
) -> None:
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL_FREE", raising=False)
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL_PRO", raising=False)
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv(env_key, env_val)
    s = Settings()
    assert resolve_gemini_model_for_tier(tier, s) == expected


def test_legacy_gemini_model_used_when_tier_specific_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL_FREE", raising=False)
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL_PRO", raising=False)
    monkeypatch.setenv("ONFLOW_GEMINI_MODEL", "legacy-model-id")
    monkeypatch.setenv("ONFLOW_GEMINI_MODEL_FREE", "")
    s = Settings()
    assert resolve_gemini_model_for_tier("free", s) == "legacy-model-id"


def test_pro_falls_back_to_legacy_then_free_model_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL_FREE", raising=False)
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL_PRO", raising=False)
    monkeypatch.delenv("ONFLOW_GEMINI_MODEL", raising=False)
    monkeypatch.setenv("ONFLOW_GEMINI_MODEL_PRO", "")
    monkeypatch.setenv("ONFLOW_GEMINI_MODEL", "")
    s = Settings(
        gemini_api_key="x",
        gemini_model_pro="",
        gemini_model_free="only-free-left",
        gemini_model="",
    )
    assert resolve_gemini_model_for_tier("pro", s) == "only-free-left"
