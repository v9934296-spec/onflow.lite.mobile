from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.rate_limit import beta_event_limit_per_minute, limiter, signed_in_user_key
from app.deps.auth import get_current_user_id
from app.schemas.beta_events import ClientBetaEventRequest, ClientBetaEventResponse
from app.services.beta_observability import log_beta

router = APIRouter(prefix="/api/v1/beta", tags=["beta"])

_SHARE_KINDS = frozenset(
    {
        "share_initiated",
        "share_completed",
        "share_failed",
        "share_install_attributed",
    }
)


@router.post("/client-events", response_model=ClientBetaEventResponse)
@limiter.limit(beta_event_limit_per_minute, key_func=signed_in_user_key)
def post_client_event(
    request: Request,
    body: ClientBetaEventRequest,
    user_id: str = Depends(get_current_user_id),
) -> ClientBetaEventResponse:
    """
    First-party client funnel pings.

    All allowlisted kinds are persisted to ``client_funnel_events`` for launch
    observability (no third-party analytics required). Share kinds remain
    available for admin share aggregates.
    """
    jid = body.job_id.strip() if body.job_id else None
    log_beta(
        "beta_client_event",
        kind=body.kind,
        user_id=user_id,
        job_id=jid,
        share_target=body.share_target,
        error_detail=(body.error_detail[:200] if body.error_detail else None),
        ref_source=body.ref_source,
    )
    db = request.app.state.db
    db.record_funnel_event(
        user_id,
        body.kind,
        job_id=jid,
        share_target=body.share_target,
        error_detail=body.error_detail,
        ref_source=body.ref_source,
    )
    # Keep _SHARE_KINDS referenced so share-admin docs stay accurate.
    _ = body.kind in _SHARE_KINDS
    return ClientBetaEventResponse()
