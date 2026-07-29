"""Canonical landing-status normalization and precedence rules."""
from __future__ import annotations

from typing import Literal

LandedStatus = Literal["yes", "no", "unclear"]


def normalize_landed_signal(raw: object) -> LandedStatus:
    """
    Normalize heterogeneous landing values to yes/no/unclear.

    A bare boolean is NOT enough evidence to claim a confident landing —
    booleans (and any non-string sentinel) collapse to "unclear" so the
    product never surfaces a fabricated "trick landed" claim from a raw
    placeholder/default. Only explicit string signals like "landed",
    "yes", "clean", "true" resolve to "yes"; only explicit negatives like
    "no", "failed", "bailed", "false" resolve to "no".

    The bool check must come BEFORE any int/string handling because
    `bool` is a subclass of `int` in Python and would otherwise match
    numeric or membership coercions.
    """
    if isinstance(raw, bool):
        return "unclear"
    if raw is None:
        return "unclear"
    if not isinstance(raw, str):
        return "unclear"

    val = raw.strip().lower()
    if not val:
        return "unclear"
    if val in ("yes", "y", "landed", "make", "made", "clean", "true"):
        return "yes"
    if val in ("no", "n", "missed", "bail", "bailed", "failed", "false"):
        return "no"
    if val in ("unclear", "unknown", "maybe"):
        return "unclear"
    return "unclear"


def resolve_landed_status(
    primary_signal: object,
    enrichment_signal: object,
) -> LandedStatus:
    """
    Single source of truth:
    - primary yes/no wins
    - enrichment yes/no is fallback
    - otherwise unclear
    """
    p = normalize_landed_signal(primary_signal)
    if p in ("yes", "no"):
        return p

    e = normalize_landed_signal(enrichment_signal)
    if e in ("yes", "no"):
        return e

    if p == "unclear" or e == "unclear":
        return "unclear"
    return "unclear"
