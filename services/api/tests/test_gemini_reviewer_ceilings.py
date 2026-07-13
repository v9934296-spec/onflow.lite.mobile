"""
Tests for GeminiReviewer's hard ceilings (retry count, max output tokens, call timeout).

These cover the helper that wraps each Gemini API call so a pathological clip or a
Gemini hiccup cannot blow through quota or hang the worker indefinitely. The test
helper bypasses the real google-genai client by exercising _call_with_ceiling
directly with a mock async callable; the production caller (GeminiReviewer.enrich)
delegates to the same helper.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.gemini_reviewer import (
    GEMINI_CALL_TIMEOUT_SECONDS,
    MAX_OUTPUT_TOKENS,
    MAX_RETRIES,
    GeminiReviewerExhaustedError,
    _call_with_ceiling,
)


def test_module_level_ceilings_are_defined() -> None:
    # The audit's specific concern: ceilings must be module-level constants,
    # not magic numbers buried in the function body, so they're explicit and reviewable.
    assert isinstance(MAX_RETRIES, int) and MAX_RETRIES >= 1
    assert isinstance(MAX_OUTPUT_TOKENS, int) and MAX_OUTPUT_TOKENS >= 1024
    assert isinstance(GEMINI_CALL_TIMEOUT_SECONDS, (int, float))
    assert GEMINI_CALL_TIMEOUT_SECONDS > 0


async def test_call_with_ceiling_caps_attempts_and_raises_typed_exception() -> None:
    # 3 transient failures → MAX_RETRIES = 3 attempts total → no 4th attempt.
    calls = 0

    async def always_fails() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("transient failure")

    with pytest.raises(GeminiReviewerExhaustedError) as ei:
        await _call_with_ceiling(
            always_fails,
            clip_label="kickflip",
            user_id="user-abc",
            backoff_base_seconds=0.0,
        )

    assert calls == MAX_RETRIES
    assert ei.value.attempts == MAX_RETRIES
    assert ei.value.reason == "transient_failures"
    assert isinstance(ei.value.last_error, RuntimeError)


async def test_call_with_ceiling_returns_after_one_transient_failure() -> None:
    # Recovery path: a single hiccup must not exhaust the retry budget; the second
    # attempt's success should be returned to the caller untouched.
    calls = 0

    async def fails_once_then_succeeds() -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("brief hiccup")
        return {"ok": "true"}

    result = await _call_with_ceiling(
        fails_once_then_succeeds,
        clip_label="ollie",
        user_id="user-xyz",
        backoff_base_seconds=0.0,
    )

    assert result == {"ok": "true"}
    assert calls == 2


async def test_call_with_ceiling_raises_on_per_attempt_timeout() -> None:
    # Each attempt is wrapped in asyncio.wait_for so a hung Gemini response cannot
    # extend a job indefinitely. After all attempts time out, a typed exception
    # surfaces — never silently swallowed.
    calls = 0

    async def hangs_forever() -> None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(10)

    with pytest.raises(GeminiReviewerExhaustedError) as ei:
        await _call_with_ceiling(
            hangs_forever,
            clip_label="hardflip",
            user_id="user-timeout",
            timeout_seconds=0.05,
            backoff_base_seconds=0.0,
        )

    assert calls == MAX_RETRIES
    assert ei.value.reason == "timeout"
    assert ei.value.attempts == MAX_RETRIES
    assert isinstance(ei.value.last_error, asyncio.TimeoutError)


async def test_exhausted_error_message_includes_attempt_count() -> None:
    async def always_fails() -> None:
        raise RuntimeError("nope")

    with pytest.raises(GeminiReviewerExhaustedError) as ei:
        await _call_with_ceiling(
            always_fails,
            clip_label="lbl",
            user_id=None,
            backoff_base_seconds=0.0,
        )

    msg = str(ei.value)
    assert str(MAX_RETRIES) in msg
    assert "transient_failures" in msg
