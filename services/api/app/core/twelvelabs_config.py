"""
Unified Twelve Labs configuration for Pro-tier Pegasus clip analysis.

Canonical env var: ONFLOW_TWELVELABS_API_KEY (loaded via Settings only).
"""

from __future__ import annotations

from app.core.config import get_settings


class TwelveLabsNotConfiguredError(RuntimeError):
    """Raised when no Twelve Labs API key is available in the environment."""


def get_twelvelabs_api_key() -> str:
    key = (get_settings().twelvelabs_api_key or "").strip()
    if key:
        return key
    raise TwelveLabsNotConfiguredError(
        "No Twelve Labs API key found. Set ONFLOW_TWELVELABS_API_KEY in the "
        "environment (Railway variables for production, .env for local)."
    )
