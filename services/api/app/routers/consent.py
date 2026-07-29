"""Consent status and grant (store + GDPR proof via consent_events)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user
from app.models import UserModel
from app.schemas.consent import ConsentGrantRequest, ConsentGrantResponse, ConsentStatus

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


def consent_status_from_user(user: UserModel | None) -> ConsentStatus:
    if user is None:
        return ConsentStatus(
            granted=False,
            granted_at=None,
            copy_version=None,
            source=None,
        )
    granted = user.consent_granted_at is not None
    ga = user.consent_granted_at
    granted_at = ga.isoformat().replace("+00:00", "Z") if ga else None
    return ConsentStatus(
        granted=granted,
        granted_at=granted_at,
        copy_version=user.consent_copy_version,
        source=user.consent_source,
    )


@router.get("", response_model=ConsentStatus)
def get_consent_status(
    request: Request,
    user_id: str = Depends(get_current_user),
) -> ConsentStatus:
    db = request.app.state.db
    user = db.get_user(user_id)
    return consent_status_from_user(user)


@router.post("/grant", response_model=ConsentGrantResponse)
def grant_consent(
    request: Request,
    body: ConsentGrantRequest,
    user_id: str = Depends(get_current_user),
) -> ConsentGrantResponse:
    db = request.app.state.db
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    ua = request.headers.get("user-agent")
    user = db.grant_consent(
        user_id,
        copy_version=body.copy_version.strip(),
        source="app",
        ip_address=ip,
        user_agent=ua,
    )
    return ConsentGrantResponse(status=consent_status_from_user(user))
