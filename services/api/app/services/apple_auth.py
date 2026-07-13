"""Verify Apple Sign In ID tokens using Apple's JWKS (cached 24h in-process)."""
from __future__ import annotations

import json
import time

import httpx
import jwt
from jwt import PyJWTError

from app.core.config import get_settings


class AppleAuthError(Exception):
    """Invalid, expired, or untrusted Apple ID token."""


_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"
_JWKS_TTL_SEC = 24 * 3600
_jwks_cache: dict[str, object] = {"expires_at": 0.0, "payload": None}


def _get_apple_jwks() -> dict:
    now = time.time()
    exp = float(_jwks_cache["expires_at"] or 0)
    if _jwks_cache["payload"] is None or now > exp:
        r = httpx.get(_APPLE_JWKS_URL, timeout=15.0)
        r.raise_for_status()
        _jwks_cache["payload"] = r.json()
        _jwks_cache["expires_at"] = now + _JWKS_TTL_SEC
    return _jwks_cache["payload"]  # type: ignore[return-value]


def verify_apple_id_token(token: str) -> dict:
    """Verify Apple ID token (RS256, iss, aud, exp). Audience from ONFLOW_APPLE_BUNDLE_ID."""
    raw = (token or "").strip()
    if not raw:
        raise AppleAuthError("empty token")

    settings = get_settings()
    audience = (settings.apple_bundle_id or "").strip() or "skate.onflow.mobile"

    try:
        hdr = jwt.get_unverified_header(raw)
    except PyJWTError as e:
        raise AppleAuthError(str(e)) from e

    kid = hdr.get("kid")
    if not kid:
        raise AppleAuthError("missing kid")

    jwks = _get_apple_jwks()
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list):
        raise AppleAuthError("invalid JWKS")

    key_data = next((k for k in keys if isinstance(k, dict) and k.get("kid") == kid), None)
    if not key_data:
        raise AppleAuthError("signing key not found")

    try:
        pub = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))
        payload = jwt.decode(
            raw,
            pub,
            algorithms=["RS256"],
            audience=audience,
            issuer=_APPLE_ISSUER,
            options={"verify_exp": True},
        )
    except PyJWTError as e:
        raise AppleAuthError(str(e)) from e

    return payload
