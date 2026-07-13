"""JWT invite codes and Bearer resolution (session token or JWT)."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def normalize_invite_code(s: str) -> str:
    """Match apps/mobile/lib/betaAccess.ts normalizeBetaCodeToken (hyphens kept, spaces stripped)."""
    t = s.strip()
    for z in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        t = t.replace(z, "")
    t = re.sub(r"[\s\u00a0]+", "", t)
    return t.upper()


def _configured_codes() -> set[str]:
    """Parse ONFLOW_BETA_CODES into a set of uppercase invite codes."""
    raw = get_settings().beta_codes.strip()
    if not raw:
        return set()
    return {normalize_invite_code(c) for c in raw.split(",") if c.strip()}


def _configured_pro_codes() -> set[str]:
    raw = get_settings().beta_pro_codes.strip()
    if not raw:
        return set()
    return {normalize_invite_code(c) for c in raw.split(",") if c.strip()}


def is_beta_user(user_id: str) -> bool:
    """Check whether a user id matches one of the configured beta invite codes."""
    uid = (user_id or "").strip()
    if not uid:
        return False
    for code in _configured_codes():
        if hashlib.sha256(code.encode()).hexdigest()[:16] == uid:
            return True
    return False


def get_user_tier_for_beta(user_id: str, fallback_tier: str) -> str:
    """
    Beta users always get Pro tier.
    Non-beta users keep their caller-provided tier.
    """
    return "pro" if is_beta_user(user_id) else fallback_tier


def issue_onflow_access_token(user_id: str) -> str:
    """
    Issue a Bearer token for an existing user id.

    Production: HS256 JWT only (never ``dev:…``). Development without secret: ``dev:…`` for local use.
    """
    settings = get_settings()
    secret = settings.jwt_secret.strip()
    if not secret:
        if settings.is_production:
            raise HTTPException(
                status_code=500,
                detail="Server misconfiguration: JWT signing is required in production.",
            )
        logger.warning("ONFLOW_JWT_SECRET not set — returning unsigned dev token")
        return f"dev:{user_id}"
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def claim_invite_code(code: str) -> str:
    """
    Validate an invite code and return a JWT (or dev token when JWT secret unset).
    """
    settings = get_settings()
    secret = settings.jwt_secret.strip()

    codes = _configured_codes()
    norm = normalize_invite_code(code)

    if codes and norm not in codes:
        raise HTTPException(status_code=422, detail="Invalid invite code.")

    if not code.strip():
        raise HTTPException(status_code=422, detail="Invite code is required.")

    user_id = hashlib.sha256(norm.encode()).hexdigest()[:16]

    if not secret:
        if settings.is_production:
            raise HTTPException(
                status_code=500,
                detail="Server misconfiguration: JWT signing is required in production.",
            )
        logger.warning("ONFLOW_JWT_SECRET not set — returning unsigned dev token")
        return f"dev:{user_id}"

    payload = {
        "sub": user_id,
        "code": norm,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def assert_optional_invite_code_valid(invite_code: str | None) -> None:
    """When ONFLOW_BETA_CODES is non-empty, a provided invite_code must match the list."""
    if not invite_code or not str(invite_code).strip():
        return
    cfg = _configured_codes()
    if cfg and normalize_invite_code(invite_code) not in cfg:
        raise HTTPException(status_code=422, detail="Invalid invite code.")


def is_beta_pro_code(code: str) -> bool:
    norm = normalize_invite_code(code)
    # All configured beta codes are Pro for closed-beta; explicit pro list is kept
    # for backward-compatible local/test overrides.
    return norm in _configured_codes() or norm in _configured_pro_codes()


def resolve_user_id_from_token(request: Request, token: str) -> str:
    """Resolve a Bearer token string to a user id (shared by REST and SSE auth)."""
    settings = get_settings()
    secret = settings.jwt_secret.strip()
    db = request.app.state.db
    cleaned = token.strip()
    if not cleaned:
        raise HTTPException(
            status_code=401,
            detail="Sign in again — missing session. Use POST /api/v1/auth/session first.",
        )

    uid = db.validate_token(cleaned)
    if uid:
        return uid

    if secret:
        try:
            payload = jwt.decode(cleaned, secret, algorithms=["HS256"])
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token payload.")
            uid = str(user_id)
            row = db.get_user(uid)
            if row and row.tokens_invalidated_at is not None:
                inv = row.tokens_invalidated_at
                if inv.tzinfo is None:
                    inv = inv.replace(tzinfo=timezone.utc)
                iat = payload.get("iat")
                if iat is None:
                    raise HTTPException(
                        status_code=401,
                        detail="Session revoked — sign in again.",
                    )
                issued = datetime.fromtimestamp(float(iat), tz=timezone.utc)
                if issued < inv:
                    raise HTTPException(
                        status_code=401,
                        detail="Session revoked — sign in again.",
                    )
            return uid
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired.")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token.")

    if cleaned.startswith("dev:"):
        if settings.is_production:
            raise HTTPException(
                status_code=401,
                detail="Invalid or unknown session. Sign in again from the app.",
            )
        return cleaned[4:]

    raise HTTPException(
        status_code=401,
        detail="Invalid or unknown session. Sign in again from the app.",
    )


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """
    Session token (SQLite) first, then signed JWT when ONFLOW_JWT_SECRET is set.

    ``dev:…`` tokens are allowed only in non-production environments when JWT secret is unset.
    """
    if not creds or not creds.credentials.strip():
        raise HTTPException(
            status_code=401,
            detail="Sign in again — missing session. Use POST /api/v1/auth/session first.",
        )
    return resolve_user_id_from_token(request, creds.credentials)


def get_current_user_sse(
    request: Request,
    token: str | None = Query(default=None),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """SSE auth: Bearer header or ``?token=`` query param (EventSource-friendly)."""
    if creds and creds.credentials.strip():
        return resolve_user_id_from_token(request, creds.credentials)
    if token and token.strip():
        return resolve_user_id_from_token(request, token)
    raise HTTPException(
        status_code=401,
        detail="Sign in again — missing session. Use POST /api/v1/auth/session first.",
    )


def bearer_identity_for_rate_limit(request: Request) -> str | None:
    """Stable user id from Bearer token for rate-limit keys (no HTTP errors)."""
    settings = get_settings()
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    db = request.app.state.db
    uid = db.validate_token(token)
    if uid:
        return uid
    secret = settings.jwt_secret.strip()
    if secret:
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            sub = payload.get("sub")
            return str(sub) if sub else None
        except jwt.InvalidTokenError:
            return None
    if token.startswith("dev:"):
        if settings.is_production:
            return None
        return token[4:]
    return None
