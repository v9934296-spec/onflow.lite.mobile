from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine
from app.models import ClipJobModel


def check_analysis_quota(user_id: str) -> None:
    """
    Hard abuse caps (rolling windows) — independent of billing tier and clip_quota.

    Values come from Settings (``clip_rate_limit_per_hour``, ``clip_rate_limit_per_day``).
    Product monthly/bonus limits are enforced separately in ``reserve_clip_submission``.
    """
    settings = get_settings()
    daily_cap = max(1, settings.clip_rate_limit_per_day)
    hourly_cap = max(1, settings.clip_rate_limit_per_hour)

    now = datetime.now(timezone.utc)
    daily_since = now - timedelta(days=1)
    hourly_since = now - timedelta(hours=1)

    with Session(get_engine()) as db:
        daily_count = db.exec(
            select(func.count(ClipJobModel.id)).where(
                ClipJobModel.user_id == user_id,
                ClipJobModel.created_at >= daily_since,
            )
        ).one()
        if int(daily_count) >= daily_cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="daily_analysis_cap_reached",
            )

        hourly_count = db.exec(
            select(func.count(ClipJobModel.id)).where(
                ClipJobModel.user_id == user_id,
                ClipJobModel.created_at >= hourly_since,
            )
        ).one()
        if int(hourly_count) >= hourly_cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="hourly_analysis_cap_reached",
            )
