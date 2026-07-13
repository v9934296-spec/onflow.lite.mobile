"""
Session-level guards for the Gemini regression suite.

These run once per pytest session when GEMINI_REGRESSION_ENABLED=1.
Their job is to prevent the "passing suite that tests nothing" failure mode,
which is worse than a red suite because it manufactures false confidence in
the trust architecture.

Import-side-effect free: the module loads without running any checks. The
checks fire via autouse session fixture only when regression mode is on.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import pytest

from app.core.gemini_config import GeminiNotConfiguredError, get_gemini_api_key
from app.services.gemini_prompt import PROMPT_VERSION

REGRESSION_ENABLED = os.getenv("GEMINI_REGRESSION_ENABLED") == "1"

REGISTRY_PATH = Path(__file__).parent / "fixtures" / "registry.json"

# Bump this when you have REVIEWED every fixture contract against the new
# prompt. A mismatch between this and PROMPT_VERSION is intentional friction:
# it forces a human to confirm the moat still holds after a prompt edit.
EXPECTED_PROMPT_VERSION = "2026-05-17"


@pytest.fixture(scope="session", autouse=True)
def _regression_session_guards() -> None:
    """
    Guards that must pass before any regression test runs. These fail the
    entire session loudly rather than letting tests skip silently to green.
    """
    if not REGRESSION_ENABLED:
        yield
        return

    _guard_registry_non_empty()
    _guard_prompt_version_pinned()
    _guard_api_key_present()

    yield


def _guard_registry_non_empty() -> None:
    """
    Refuse to report green on zero assertions. If the suite is enabled but
    the registry is empty, that's a config error, not a clean run.
    """
    if not REGISTRY_PATH.is_file():
        pytest.fail(
            f"GEMINI_REGRESSION_ENABLED=1 but registry file is missing: {REGISTRY_PATH}",
            pytrace=False,
        )
    try:
        with REGISTRY_PATH.open(encoding="utf-8") as f:
            registry = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        pytest.fail(
            f"GEMINI_REGRESSION_ENABLED=1 but registry could not be read: {REGISTRY_PATH} ({exc})",
            pytrace=False,
        )
    fixtures = registry.get("fixtures", [])
    if not fixtures:
        pytest.fail(
            "GEMINI_REGRESSION_ENABLED=1 but fixtures/registry.json is empty. "
            "Refusing to report green on zero assertions. "
            "Add at least one fixture before running the regression suite.",
            pytrace=False,
        )


def _guard_prompt_version_pinned() -> None:
    """
    Force human review of fixture contracts when the prompt changes.

    The failure mode this prevents: someone edits the system prompt to fix
    one issue, the suite passes because fixtures don't happen to cover the
    regression it introduced, and the moat silently leaks.
    """
    if PROMPT_VERSION != EXPECTED_PROMPT_VERSION:
        pytest.fail(
            f"System prompt version changed ({EXPECTED_PROMPT_VERSION!r} -> "
            f"{PROMPT_VERSION!r}) without a corresponding update to the "
            f"regression fixture contracts. "
            f"Re-review every fixture in registry.json against the new "
            f"prompt, then bump EXPECTED_PROMPT_VERSION in this file to "
            f"{PROMPT_VERSION!r}.",
            pytrace=False,
        )


def _guard_api_key_present() -> None:
    """
    Unified API key read. ONFLOW_GEMINI_API_KEY is canonical; GEMINI_API_KEY
    is the deprecated alias and emits a warning. Having two env var names
    for the same secret is how 11pm prod incidents start.
    """
    canonical = os.getenv("ONFLOW_GEMINI_API_KEY", "").strip()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            _ = get_gemini_api_key()
    except GeminiNotConfiguredError:
        pytest.fail(
            "ONFLOW_GEMINI_API_KEY is not set. Regression suite requires a "
            "live Gemini key because the risk it guards against is model/"
            "prompt drift, which a mock cannot detect.",
            pytrace=False,
        )
    legacy_only = (not canonical) and any(
        isinstance(w.message, DeprecationWarning) for w in caught
    )
    if legacy_only:
        pytest.fail(
            "GEMINI_API_KEY is deprecated for regression runs. Set "
            "ONFLOW_GEMINI_API_KEY instead.",
            pytrace=False,
        )
