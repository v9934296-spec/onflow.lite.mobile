"""
Slowapi rate limits for abuse / spam protection.

**Product quota** (monthly free tier, bonus credits, Pro unlimited) lives in ``clip_quota`` —
separate from these ceilings.

**Security throttles here must not** change Gemini model choice, tier normalization, or
analysis quality — only request volume. Tier → model routing stays in ``app.core.tiers``.

Production/staging: ``ONFLOW_REDIS_URL`` is required (see ``Settings.requires_distributed_rate_limits``).
slowapi uses Redis-backed storage; there is no silent per-replica memory fallback.

Development: in-memory slowapi storage when Redis is unset; delete-account may use Redis or memory.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Literal

from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth import bearer_identity_for_rate_limit
from app.core.config import get_settings

_log = logging.getLogger(__name__)

RateLimitStorage = Literal["redis", "memory"]
RATE_LIMIT_STORAGE: RateLimitStorage = "memory"

# --- Key helpers (prefer named functions over inline lambdas) ---


def remote_ip_key(request: Request) -> str:
    """Client IP for unauthenticated or IP-scoped routes (auth invite, OAuth, webhooks)."""
    return f"ip:{get_remote_address(request)}"


def signed_in_user_key(request: Request) -> str:
    """Stable key for Bearer JWT / session users; falls back to IP if no Bearer identity."""
    uid = bearer_identity_for_rate_limit(request)
    if uid:
        return f"uid:{uid}"
    return f"ip:{get_remote_address(request)}"


def clip_submission_key(request: Request) -> str:
    """Clip job POST: prefer authenticated user, else IP (matches prior behavior)."""
    uid = bearer_identity_for_rate_limit(request)
    if uid:
        return f"user:{uid}"
    return f"ip:{get_remote_address(request)}"


def rate_limit_storage_mode() -> RateLimitStorage:
    """Current slowapi backend selected at import time."""
    return RATE_LIMIT_STORAGE


def _make_limiter() -> Limiter:
    global RATE_LIMIT_STORAGE
    settings = get_settings()
    redis_url = (settings.redis_url or "").strip()

    if redis_url:
        RATE_LIMIT_STORAGE = "redis"
        _log.info("Rate limiter storage: redis (ONFLOW_REDIS_URL configured)")
        return Limiter(
            key_func=clip_submission_key,
            default_limits=[],
            storage_uri=redis_url,
        )

    if settings.requires_distributed_rate_limits:
        # Settings validator should prevent this; guard for mis-ordered imports.
        raise RuntimeError(
            "Rate limiter misconfiguration: production/staging requires ONFLOW_REDIS_URL. "
            "In-memory slowapi storage is not allowed with multiple API replicas."
        )

    RATE_LIMIT_STORAGE = "memory"
    _log.warning(
        "Rate limiter storage: memory (development fallback). "
        "Do not run multiple replicas without ONFLOW_REDIS_URL."
    )
    return Limiter(key_func=clip_submission_key, default_limits=[])


limiter = _make_limiter()


def validate_rate_limit_storage_at_startup() -> None:
    """
    After app settings are loaded: ensure Redis is reachable when required.

    Skips the connectivity check under pytest (CI may not run Redis); production Railway must pass.
    """
    settings = get_settings()
    if not (settings.redis_url or "").strip():
        if settings.requires_distributed_rate_limits:
            raise RuntimeError(
                "ONFLOW_REDIS_URL is required in production/staging but is not configured."
            )
        _log.info("Rate limiter storage: memory (development fallback)")
        return

    if os.environ.get("PYTEST_CURRENT_TEST"):
        _log.info(
            "Rate limiter storage: %s (pytest — skipping Redis connectivity check)",
            RATE_LIMIT_STORAGE,
        )
        return

    client = _get_redis()
    if client is None:
        msg = (
            "ONFLOW_REDIS_URL is set but Redis is unreachable. "
            "Fix Redis before serving traffic (rate limits and ARQ depend on it)."
        )
        if settings.requires_distributed_rate_limits:
            raise RuntimeError(msg)
        _log.warning(msg)
        return

    _log.info("Rate limiter storage: redis (connectivity check passed)")


# --- Clip abuse (slowapi): hourly + daily caps; values from Settings ---


def clip_abuse_limit_per_hour(key: str) -> str:
    _ = key
    return f"{get_settings().clip_rate_limit_per_hour}/hour"


def clip_abuse_limit_per_day(key: str) -> str:
    _ = key
    return f"{get_settings().clip_rate_limit_per_day}/day"


# --- Auth: claim + session (same IP limits) ---


def auth_invite_limit_per_minute(key: str) -> str:
    _ = key
    return f"{get_settings().auth_rate_limit_per_minute}/minute"


def auth_invite_limit_per_hour(key: str) -> str:
    _ = key
    return f"{get_settings().auth_rate_limit_per_hour}/hour"


# --- OAuth (Google / Apple) ---


def oauth_limit_per_minute(key: str) -> str:
    _ = key
    return f"{get_settings().oauth_rate_limit_per_minute}/minute"


# --- Feedback / beta events ---


def feedback_limit_per_minute(key: str) -> str:
    _ = key
    return f"{get_settings().feedback_rate_limit_per_minute}/minute"


def beta_event_limit_per_minute(key: str) -> str:
    _ = key
    return f"{get_settings().beta_event_rate_limit_per_minute}/minute"


# --- Account ---


def export_limit_per_hour(key: str) -> str:
    _ = key
    return f"{get_settings().export_rate_limit_per_hour}/hour"


# --- Webhooks (lenient; verification remains primary) ---


def webhook_limit_per_minute(key: str) -> str:
    _ = key
    return f"{get_settings().webhook_rate_limit_per_minute}/minute"


# Account delete: rolling window keyed by **user id** (not Bearer string).
# Applied only when a destructive delete runs — idempotent 202s (already deleted / pending)
# do not consume the limit. Separate from product quota and from Gemini/tier routing.
#
# Production/staging: Redis only (no in-process fallback). Development: memory when Redis absent.
_delete_account_hits: dict[str, list[float]] = defaultdict(list)

_redis_client: object | None = None  # cached redis.Redis once we successfully PING it


def _get_redis() -> object | None:
    """Return a sync Redis client if ONFLOW_REDIS_URL is set and reachable, else None."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = (get_settings().redis_url or "").strip()
    if not redis_url:
        return None
    try:
        import redis as _redis  # type: ignore[import]

        client = _redis.from_url(
            redis_url, decode_responses=True, socket_timeout=1.0
        )
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception:
        return None


def enforce_delete_account_rate_limit(user_id: str) -> None:
    """Raise 429 when this user id has exceeded configured deletes per rolling 24h.

    Uses Redis INCR+EXPIRE when available (multi-replica safe). In production/staging,
    Redis is mandatory — no silent in-process fallback.
    """
    settings = get_settings()
    cap = max(0, settings.delete_account_rate_limit_per_day)
    if cap <= 0:
        return

    r = _get_redis()
    if r is not None:
        redis_key = f"onflow:delete_acct:{user_id}"
        try:
            count = r.incr(redis_key)  # type: ignore[attr-defined]
            if count == 1:
                r.expire(redis_key, 86400)  # type: ignore[attr-defined]
            if count > cap:
                raise HTTPException(
                    status_code=429,
                    detail="Delete account rate limit exceeded.",
                )
            return
        except HTTPException:
            raise
        except Exception as exc:
            if settings.requires_distributed_rate_limits:
                _log.error(
                    "delete_account_rate_limit_redis_error user_id=%s error=%s",
                    user_id,
                    exc,
                )
                raise HTTPException(
                    status_code=503,
                    detail="Delete account is temporarily unavailable. Try again later.",
                ) from exc
            _log.warning(
                "delete_account_rate_limit_redis_error user_id=%s — using dev memory fallback",
                user_id,
            )

    if settings.requires_distributed_rate_limits:
        _log.error(
            "delete_account_rate_limit_no_redis user_id=%s — refusing in-process fallback",
            user_id,
        )
        raise HTTPException(
            status_code=503,
            detail="Delete account is temporarily unavailable. Try again later.",
        )

    key = f"uid:{user_id}"
    now = time.time()
    window = 86400.0
    hits = _delete_account_hits[key]
    hits[:] = [t for t in hits if now - t < window]
    if len(hits) >= cap:
        raise HTTPException(
            status_code=429,
            detail="Delete account rate limit exceeded.",
        )
    hits.append(now)
