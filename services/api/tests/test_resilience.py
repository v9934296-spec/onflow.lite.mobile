"""Tests for retry and circuit breaker."""
from __future__ import annotations

import time

import pytest

from app.core.resilience import CircuitBreaker, retry_async


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt() -> None:
    call_count = 0

    async def flaky() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("transient")
        return "ok"

    result = await retry_async(flaky, max_attempts=3, base_delay=0.01)
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_exhausted_raises() -> None:
    async def always_fail() -> None:
        raise ValueError("permanent")

    with pytest.raises(ValueError, match="permanent"):
        await retry_async(always_fail, max_attempts=2, base_delay=0.01)


def test_circuit_breaker_trips_after_threshold() -> None:
    cb = CircuitBreaker(threshold=3, window_seconds=60.0, cooldown_seconds=0.1)
    assert not cb.is_open
    cb.record_failure()
    cb.record_failure()
    assert not cb.is_open
    cb.record_failure()
    assert cb.is_open


def test_circuit_breaker_resets_after_cooldown() -> None:
    cb = CircuitBreaker(threshold=2, window_seconds=60.0, cooldown_seconds=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open
    time.sleep(0.15)
    assert not cb.is_open


def test_circuit_breaker_success_clears_failures() -> None:
    cb = CircuitBreaker(threshold=3, window_seconds=60.0, cooldown_seconds=300.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    assert not cb.is_open
