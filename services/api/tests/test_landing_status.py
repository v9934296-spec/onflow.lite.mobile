from __future__ import annotations

from app.services.landing_status import normalize_landed_signal, resolve_landed_status


def test_normalize_landed_signal_booleans_default_unclear() -> None:
    # A bare boolean is not evidence of a confident landing — collapse to "unclear"
    # so we never surface a fabricated "landed" claim from a raw placeholder/default.
    assert normalize_landed_signal(True) == "unclear"
    assert normalize_landed_signal(False) == "unclear"


def test_resolve_landed_status_primary_yes_no_wins() -> None:
    assert resolve_landed_status("yes", "unclear") == "yes"
    assert resolve_landed_status("no", "yes") == "no"


def test_resolve_landed_status_uses_enrichment_when_primary_missing() -> None:
    assert resolve_landed_status(None, "yes") == "yes"
    assert resolve_landed_status(None, "no") == "no"


def test_resolve_landed_status_defaults_unclear_when_both_missing() -> None:
    assert resolve_landed_status(None, None) == "unclear"
