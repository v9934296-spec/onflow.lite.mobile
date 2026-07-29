"""
Unified Gemini configuration.

Canonical env var: ONFLOW_GEMINI_API_KEY
Deprecated alias: GEMINI_API_KEY (will be removed; emits warning)

All Gemini-related config reads go through this module. Do not call
os.getenv("GEMINI_API_KEY") directly anywhere else in the codebase.
"""

from __future__ import annotations

import os
import warnings


class GeminiNotConfiguredError(RuntimeError):
    """Raised when no Gemini API key is available in the environment."""


def get_gemini_api_key() -> str:
    """
    Return the configured Gemini API key.

    Raises GeminiNotConfiguredError if neither variable is set. Emits a
    DeprecationWarning if only the legacy name is set.
    """
    canonical = os.getenv("ONFLOW_GEMINI_API_KEY")
    if canonical:
        return canonical

    legacy = os.getenv("GEMINI_API_KEY")
    if legacy:
        warnings.warn(
            "GEMINI_API_KEY is deprecated. Rename to ONFLOW_GEMINI_API_KEY. "
            "Support for the legacy name will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy

    raise GeminiNotConfiguredError(
        "No Gemini API key found. Set ONFLOW_GEMINI_API_KEY in the "
        "environment (Railway variables for production, .env for local)."
    )
