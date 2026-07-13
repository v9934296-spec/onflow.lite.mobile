"""Retry and circuit breaker for external API calls (Gemini)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    **kwargs: Any,
) -> T:
    """Retry an async function with exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Retry %d/%d after %.1fs: %s",
                    attempt + 1,
                    max_attempts,
                    delay,
                    str(exc)[:200],
                )
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


class CircuitBreaker:
    """
    Simple circuit breaker. Trips after `threshold` consecutive failures
    within `window_seconds`. Resets after `cooldown_seconds`.
    """

    def __init__(
        self,
        threshold: int = 5,
        window_seconds: float = 60.0,
        cooldown_seconds: float = 300.0,
    ) -> None:
        self._threshold = threshold
        self._window = window_seconds
        self._cooldown = cooldown_seconds
        self._failures: list[float] = []
        self._tripped_at: float | None = None

    @property
    def is_open(self) -> bool:
        """True if the circuit is tripped (calls should be skipped)."""
        if self._tripped_at is None:
            return False
        if time.monotonic() - self._tripped_at >= self._cooldown:
            self.reset()
            return False
        return True

    def record_failure(self) -> None:
        now = time.monotonic()
        self._failures = [t for t in self._failures if now - t < self._window]
        self._failures.append(now)
        if len(self._failures) >= self._threshold:
            self._tripped_at = now
            logger.error(
                "Circuit breaker TRIPPED: %d failures in %.0fs. Skipping for %.0fs.",
                len(self._failures),
                self._window,
                self._cooldown,
            )

    def record_success(self) -> None:
        self._failures.clear()
        if self._tripped_at is not None:
            logger.info("Circuit breaker RESET after successful call.")
            self._tripped_at = None

    def reset(self) -> None:
        self._failures.clear()
        if self._tripped_at is not None:
            logger.info("Circuit breaker RESET (cooldown expired).")
        self._tripped_at = None


gemini_circuit = CircuitBreaker(threshold=5, window_seconds=60.0, cooldown_seconds=300.0)
