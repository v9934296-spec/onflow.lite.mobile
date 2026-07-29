"""Verify Google OAuth ID tokens (server-side only)."""
from __future__ import annotations

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import get_settings


class GoogleAuthError(Exception):
    """Invalid, expired, or untrusted Google ID token."""


def verify_google_id_token(token: str) -> dict:
    """
    Verify a Google ID token (signature, issuer, audience, expiry).
    Allowed audiences come from ONFLOW_GOOGLE_CLIENT_IDS (comma-separated).
    """
    raw = (token or "").strip()
    if not raw:
        raise GoogleAuthError("empty token")

    settings = get_settings()
    audiences = [a.strip() for a in (settings.google_client_ids or "").split(",") if a.strip()]
    if not audiences:
        raise GoogleAuthError("ONFLOW_GOOGLE_CLIENT_IDS is not configured")

    try:
        info = id_token.verify_oauth2_token(
            raw,
            google_requests.Request(),
            audience=audiences,
        )
    except ValueError as e:
        raise GoogleAuthError(str(e)) from e

    iss = info.get("iss")
    if iss != "https://accounts.google.com":
        raise GoogleAuthError("invalid issuer")

    return info
