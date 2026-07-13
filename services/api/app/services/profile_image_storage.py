"""
Profile image persistence — today inline on ``users.profile_image_url``.

See ``docs/architecture/profile-image-storage.md`` for the planned move to object storage.
"""

from __future__ import annotations

STORAGE_MODE_INLINE_DB = "inline_db_column"
"""Current production mode: base64 or stock: token stored on the user row."""

MAX_INLINE_PAYLOAD_CHARS = 350_000
"""Matches ``account._validate_profile_image_url`` — do not raise without a migration plan."""


def storage_mode() -> str:
    """Report how profile images are stored (for logs/metrics)."""
    return STORAGE_MODE_INLINE_DB
