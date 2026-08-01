"""Daily Gemini spend cap — fail-closed cost protection (Postgres/SQLite)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.models import GeminiSpendDailyModel

_log = logging.getLogger(__name__)

# Upper-bound estimates per call in USD cents.
_COST_PER_CALL_CENTS: dict[str, int] = {
    "gemini-2.5-flash-lite": 8,
    "gemini-2.5-flash": 20,
    "pegasus1.5": 25,
}


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _cap_cents() -> int:
    """0 = cap disabled (ONFLOW_GEMINI_DAILY_SPEND_CAP_USD unset or zero)."""
    usd = get_settings().gemini_daily_spend_cap_usd
    if usd is None or usd <= 0:
        return 0
    return int(round(float(usd) * 100))


def estimated_call_cost_cents(model: str) -> int:
    """Conservative per-call estimate; unknown models use Flash upper bound."""
    key = (model or "").strip()
    return _COST_PER_CALL_CENTS.get(key, 20)


def check_daily_spend_cap() -> None:
    """Raise 429 when today's recorded spend has reached the daily cap."""
    cap = _cap_cents()
    if cap <= 0:
        return

    today = _today_utc()
    with Session(get_engine()) as session:
        row = session.get(GeminiSpendDailyModel, today)
        current = row.spend_usd_cents if row else 0
        if current >= cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="High demand right now — analysis is paused. Try again in a few hours.",
            )


def record_gemini_call(model: str) -> None:
    """Record one Gemini API call's estimated cost. Best-effort; never raises."""
    try:
        cost = estimated_call_cost_cents(model)
        today = _today_utc()
        now = datetime.now(timezone.utc)
        with Session(get_engine()) as session:
            row = session.get(GeminiSpendDailyModel, today)
            if row is None:
                row = GeminiSpendDailyModel(
                    spend_date=today,
                    spend_usd_cents=cost,
                    job_count=1,
                    updated_at=now,
                )
            else:
                row.spend_usd_cents += cost
                row.job_count += 1
                row.updated_at = now
            session.add(row)
            session.commit()
    except Exception:
        _log.warning("gemini_spend_record_failed", exc_info=True)
