"""Google and Apple Sign In — exchange provider ID tokens for OnFlow JWTs."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import issue_onflow_access_token
from app.core.config import get_settings
from app.core.rate_limit import limiter, oauth_limit_per_minute, remote_ip_key
from app.repositories.identity import IdentityRepository
from app.services.apple_auth import AppleAuthError, verify_apple_id_token
from app.services.google_auth import GoogleAuthError, verify_google_id_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class ProviderTokenRequest(BaseModel):
    id_token: str = Field(..., min_length=10)


class OAuthSignInResponse(BaseModel):
    token: str
    user_id: str
    is_new_user: bool
    bonus_analyses_remaining: int


def _google_route_configured() -> None:
    if not get_settings().google_client_ids.strip():
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured (ONFLOW_GOOGLE_CLIENT_IDS).",
        )


@router.post("/google", response_model=OAuthSignInResponse)
@limiter.limit(oauth_limit_per_minute, key_func=remote_ip_key)
def sign_in_with_google(request: Request, body: ProviderTokenRequest) -> OAuthSignInResponse:
    _google_route_configured()
    try:
        info = verify_google_id_token(body.id_token)
    except GoogleAuthError as e:
        msg = str(e).lower()
        if "not configured" in msg:
            raise HTTPException(
                status_code=500,
                detail="Google OAuth is not configured (ONFLOW_GOOGLE_CLIENT_IDS).",
            ) from e
        logger.info("google token verify failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Google ID token.") from e

    sub = info.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid Google ID token.")

    email = info.get("email")
    email_str = str(email).strip() if email else ""
    if not email_str or "@" not in email_str:
        raise HTTPException(status_code=422, detail="Google did not return an email for this account.")

    if not bool(info.get("email_verified")):
        raise HTTPException(
            status_code=403,
            detail="Google email is not verified.",
        )

    db: IdentityRepository = request.app.state.db
    try:
        user_id, is_new = db.oauth_complete_signin(
            provider="google",
            sub=str(sub),
            email=email_str,
            email_verified=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    token = issue_onflow_access_token(user_id)
    bonus = db.get_bonus_analyses(user_id)
    return OAuthSignInResponse(
        token=token,
        user_id=user_id,
        is_new_user=is_new,
        bonus_analyses_remaining=bonus,
    )


@router.post("/apple", response_model=OAuthSignInResponse)
@limiter.limit(oauth_limit_per_minute, key_func=remote_ip_key)
def sign_in_with_apple(request: Request, body: ProviderTokenRequest) -> OAuthSignInResponse:
    try:
        info = verify_apple_id_token(body.id_token)
    except AppleAuthError as e:
        logger.info("apple token verify failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Apple ID token.") from e

    sub = info.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid Apple ID token.")

    raw_email = info.get("email")
    email_str = str(raw_email).strip() if raw_email else ""
    email_opt = email_str if email_str and "@" in email_str else None

    email_verified = True
    if "email_verified" in info:
        email_verified = bool(info.get("email_verified"))
    if email_opt and "email_verified" in info and not email_verified:
        raise HTTPException(
            status_code=403,
            detail="Apple email is not verified.",
        )

    db: IdentityRepository = request.app.state.db
    try:
        user_id, is_new = db.oauth_complete_signin(
            provider="apple",
            sub=str(sub),
            email=email_opt,
            email_verified=email_verified,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    token = issue_onflow_access_token(user_id)
    bonus = db.get_bonus_analyses(user_id)
    return OAuthSignInResponse(
        token=token,
        user_id=user_id,
        is_new_user=is_new,
        bonus_analyses_remaining=bonus,
    )
