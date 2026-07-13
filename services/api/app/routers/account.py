"""
Signed-in account snapshot (quota, tier).

``GET /quota`` reflects **product** tier and monthly limits (``clip_quota``). Per-route
slowapi limits on export/delete are **security** throttles only — they do not change
Gemini model or analysis quality.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, Response

from app.core.auth import get_current_user, get_user_tier_for_beta
from app.core.config import get_settings
from app.core.feature_gates import tier_has_feature
from app.core.rate_limit import (
    enforce_delete_account_rate_limit,
    export_limit_per_hour,
    limiter,
    signed_in_user_key,
)
from app.core.tiers import normalize_tier, tier_has_unlimited_analyses
from app.models import get_analyses_remaining
from app.routers.consent import consent_status_from_user
from app.schemas.consent import ConsentStatus
from app.services.deletion_queue import enqueue_hard_delete

router = APIRouter(prefix="/api/v1/account", tags=["account"])


class AccountQuotaResponse(BaseModel):
    tier: str
    analyses_remaining: int
    trial_expires_at: datetime | None = None
    subscription_status: str
    bonus_analyses: int
    monthly_free_remaining: int | None = Field(
        default=None,
        description="None when Pro/Coach (unlimited analyses).",
    )


class MeResponse(BaseModel):
    user_id: str
    email: str
    tier: str
    profile_image_url: str | None = None
    consent: ConsentStatus


class ProfileImageUpdateRequest(BaseModel):
    profile_image_url: str | None = None


def _account_deletion_queued_response() -> JSONResponse:
    return JSONResponse(
        status_code=202,
        content={
            "status": "queued",
            "message": (
                "Account deletion queued. Your clips will be permanently removed within 24 hours."
            ),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/me", response_model=MeResponse)
def get_me(
    request: Request,
    user_id: str = Depends(get_current_user),
) -> MeResponse:
    db = request.app.state.db
    u = db.get_user(user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return MeResponse(
        user_id=u.id,
        email=u.email,
        tier=u.tier,
        profile_image_url=u.profile_image_url,
        consent=consent_status_from_user(u),
    )


def _validate_profile_image_url(raw: str | None) -> str | None:
    if raw is None:
        return None
    val = raw.strip()
    if not val:
        return None
    if val.startswith("stock:"):
        return val[:64]
    if not val.startswith("data:image/") or ";base64," not in val:
        raise HTTPException(
            status_code=422,
            detail="profile_image_url must be a stock: token or data:image/*;base64 payload.",
        )
    # Keep payload bounded to avoid oversized rows.
    from app.services.profile_image_storage import MAX_INLINE_PAYLOAD_CHARS

    if len(val) > MAX_INLINE_PAYLOAD_CHARS:
        raise HTTPException(status_code=413, detail="Profile image payload is too large.")
    return val


@router.put("/profile-image", response_model=MeResponse)
def update_profile_image(
    body: ProfileImageUpdateRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
) -> MeResponse:
    db = request.app.state.db
    u = db.get_user(user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    clean = _validate_profile_image_url(body.profile_image_url)
    db.set_profile_image_url(user_id, clean)
    u = db.get_user(user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return MeResponse(
        user_id=u.id,
        email=u.email,
        tier=u.tier,
        profile_image_url=u.profile_image_url,
        consent=consent_status_from_user(u),
    )


@router.delete("", status_code=202)
async def delete_my_account(
    request: Request,
    user_id: str = Depends(get_current_user),
) -> Response:
    db = request.app.state.db
    u = db.get_user(user_id)
    if u is None:
        return _account_deletion_queued_response()
    if u.pending_deletion_at is not None:
        return _account_deletion_queued_response()
    enforce_delete_account_rate_limit(user_id)
    db.purge_user_owned_rows(user_id)
    db.delete_sessions_for_user(user_id)
    db.anonymize_user_for_deletion(user_id)
    await enqueue_hard_delete(user_id, datetime.now(timezone.utc))
    return _account_deletion_queued_response()


@router.get("/export")
@limiter.limit(export_limit_per_hour, key_func=signed_in_user_key)
def export_my_data(
    request: Request,
    user_id: str = Depends(get_current_user),
) -> dict:
    db = request.app.state.db
    repo = request.app.state.repo
    u = db.get_user(user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found.")
    # Single-query fetch — list_full_for_user replaces the previous
    # list_for_user + per-row repo.get loop, which was a 1 + N query path.
    jobs: list[dict] = [
        {
            "job_id": rec.id,
            "status": rec.status,
            "clip_label": rec.clip_label,
            "created_at": rec.created_at.isoformat().replace("+00:00", "Z"),
            "failure_reason": rec.failure_reason,
            "result": rec.result_json,
            "clip_metadata": rec.clip_metadata,
        }
        for rec in repo.list_full_for_user(user_id, limit=500)
    ]
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "user": {"id": u.id, "email": u.email, "tier": u.tier},
        "consent": consent_status_from_user(u).model_dump(),
        "clips": jobs,
        "consent_events": db.list_consent_events(user_id),
        "export_generated_at": generated_at,
        "policy_version_at_export": "v1_2026_04_14",
    }


@router.get("/quota", response_model=AccountQuotaResponse)
def get_account_quota(
    request: Request,
    user_id: str = Depends(get_current_user),
) -> AccountQuotaResponse:
    db = request.app.state.db
    repo = request.app.state.repo
    settings = get_settings()
    tier = normalize_tier(get_user_tier_for_beta(user_id, db.get_user_tier(user_id)))
    user = db.get_user(user_id)
    subscription_status = (user.subscription_status or "active") if user else "active"
    trial_expires_at = user.trial_expires_at if user and tier == "trial" else None
    bonus = db.get_bonus_analyses(user_id)
    analyses_remaining = get_analyses_remaining(user) if user else 0
    if not tier_has_feature(tier, "upload_clip"):
        return AccountQuotaResponse(
            tier=tier,
            analyses_remaining=0,
            trial_expires_at=trial_expires_at,
            subscription_status=subscription_status,
            bonus_analyses=bonus,
            monthly_free_remaining=None,
        )
    if tier_has_unlimited_analyses(tier):
        return AccountQuotaResponse(
            tier=tier,
            analyses_remaining=analyses_remaining,
            trial_expires_at=trial_expires_at,
            subscription_status=subscription_status,
            bonus_analyses=bonus,
            monthly_free_remaining=None,
        )
    used = repo.count_monthly_free_jobs(user_id)
    cap = max(1, settings.rate_limit_free)
    remaining = max(0, cap - used)
    return AccountQuotaResponse(
        tier=tier,
        analyses_remaining=remaining,
        trial_expires_at=trial_expires_at,
        subscription_status=subscription_status,
        bonus_analyses=bonus,
        monthly_free_remaining=remaining,
    )
