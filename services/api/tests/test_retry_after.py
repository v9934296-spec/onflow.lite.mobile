"""Unit tests for Retry-After derivation from slowapi details."""
from __future__ import annotations

from types import SimpleNamespace

from app.core.rate_limit import _retry_after_seconds


def test_retry_after_parses_minute_window() -> None:
    exc = SimpleNamespace(detail="Rate limit exceeded: 5 per 1 minute")
    assert _retry_after_seconds(exc) == 60


def test_retry_after_parses_hour_window() -> None:
    exc = SimpleNamespace(detail="10 per 1 hour")
    assert _retry_after_seconds(exc) == 3600


def test_retry_after_parses_day_window() -> None:
    exc = SimpleNamespace(detail="100 per 1 day")
    assert _retry_after_seconds(exc) == 86400


def test_retry_after_falls_back_to_default_not_24h() -> None:
    exc = SimpleNamespace(detail="too many requests")
    assert _retry_after_seconds(exc) == 60
    assert _retry_after_seconds(exc, default=120) == 120
