"""Admin-style aggregates (authenticated admin role required)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.deps.admin import require_admin

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/share-stats")
def share_stats(
    request: Request,
    days: int = 7,
    _admin_user_id: str = Depends(require_admin),
) -> dict:
    """
    Aggregated share funnel counts (persisted client_funnel_events).
    Requires Bearer auth for a user with users.is_admin (bootstrap via ONFLOW_ADMIN_EMAILS).
    """
    if days < 1 or days > 366:
        raise HTTPException(status_code=400, detail="days must be 1–366")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    db = request.app.state.db
    counts = db.share_funnel_counts_since(since)
    initiated = counts.get("share_initiated", 0)
    completed = counts.get("share_completed", 0)
    return {
        "window_days": days,
        "share_initiated": initiated,
        "share_completed": completed,
        "share_failed": counts.get("share_failed", 0),
        "share_install_attributed": counts.get("share_install_attributed", 0),
        "completion_rate": (completed / initiated) if initiated else 0.0,
    }
