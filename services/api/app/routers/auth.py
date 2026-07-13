from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import (
    auth_invite_limit_per_hour,
    auth_invite_limit_per_minute,
    limiter,
    remote_ip_key,
)
from app.deps.auth import get_current_user_id
from app.repositories.identity import IdentityRepository
from app.schemas.session_payloads import SessionCreateRequest, SessionCreateResponse
from app.services.beta_observability import log_beta

logger = logging.getLogger(__name__)


def _consent_at_iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).replace("Z", "+00:00", 1)
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class ClipRetentionConsentRequest(BaseModel):
    consent: bool = Field(..., description="Opt in (true) or withdraw (false) clip retention for training.")


class ClipRetentionConsentResponse(BaseModel):
    clip_retention_consent: bool
    clip_retention_consent_at: datetime | None


class ClipRetentionRequest(BaseModel):
    consent: bool


class ClipRetentionResponse(BaseModel):
    clip_retention_consent: bool
    clip_retention_consent_at: str | None = None


@router.post("/clip-retention", response_model=ClipRetentionResponse)
def post_clip_retention(
    request: Request,
    body: ClipRetentionRequest,
    user_id: str = Depends(get_current_user_id),
) -> ClipRetentionResponse:
    """
    Opt in or out of clip retention for model training.

    When consent is True: clips from completed analyses will be retained on our servers
    to improve the coaching model.

    When consent is False: clips are deleted after analysis as usual.
    Previously retained clips are NOT automatically deleted (contact support).
    """
    db: IdentityRepository = request.app.state.db
    result = db.set_clip_retention_consent(user_id, body.consent)
    return ClipRetentionResponse(
        clip_retention_consent=result["consent"],
        clip_retention_consent_at=result["consent_at"],
    )


@router.get("/clip-retention", response_model=ClipRetentionResponse)
def get_clip_retention(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> ClipRetentionResponse:
    """Current clip retention consent status (ISO timestamp string when opted in)."""
    db: IdentityRepository = request.app.state.db
    state = db.get_clip_retention_state(user_id)
    return ClipRetentionResponse(
        clip_retention_consent=state["consent"],
        clip_retention_consent_at=state["consent_at"],
    )


@router.post("/clip-retention-consent", response_model=ClipRetentionConsentResponse)
def set_clip_retention_consent_legacy(
    request: Request,
    body: ClipRetentionConsentRequest,
    current_user: str = Depends(get_current_user),
) -> ClipRetentionConsentResponse:
    """Legacy alias — same storage as POST /clip-retention (users table)."""
    db: IdentityRepository = request.app.state.db
    result = db.set_clip_retention_consent(current_user, body.consent)
    return ClipRetentionConsentResponse(
        clip_retention_consent=result["consent"],
        clip_retention_consent_at=_consent_at_iso_to_dt(result["consent_at"]),
    )


@router.post("/session", response_model=SessionCreateResponse)
@limiter.limit(auth_invite_limit_per_hour, key_func=remote_ip_key)
@limiter.limit(auth_invite_limit_per_minute, key_func=remote_ip_key)
def create_session(request: Request, body: SessionCreateRequest) -> SessionCreateResponse:
    if get_settings().is_production:
        raise HTTPException(
            status_code=403,
            detail="Email session sign-in is disabled in production.",
        )
    db: IdentityRepository = request.app.state.db
    email = body.email.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Valid email is required.")
    existing_user = db.get_user_by_email_ci(email)
    try:
        user_id, token, norm = db.create_user_session(email)
    except ValueError as e:
        log_beta("beta_sign_in_failure", reason="validation", detail=str(e)[:120])
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception:
        logger.exception("create_session failed")
        log_beta("beta_sign_in_failure", reason="internal_error")
        raise HTTPException(status_code=500, detail="Could not create session.") from None
    logger.info("session created user_id=%s", user_id)
    if existing_user is None:
        db.initialize_trial_for_new_user(user_id)
    log_beta("beta_sign_in_success", user_id=user_id)
    return SessionCreateResponse(
        user_id=user_id,
        session_token=token,
        email=norm,
    )
