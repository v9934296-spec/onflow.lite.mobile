from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_db
from app.models import ClipJobModel

router = APIRouter(tags=["health"])


def _worker_expected_flag(queue_configured: bool) -> bool:
    raw = (os.getenv("ONFLOW_CLIP_WORKER_EXPECTED") or "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return queue_configured


def clip_queue_snapshot(db: Session) -> dict[str, int | bool | None]:
    """DB-backed clip backlog (pending / processing rows), not Redis queue length."""
    now = datetime.now(timezone.utc)
    settings = get_settings()
    queue_configured = bool((settings.redis_url or "").strip())
    worker_expected = _worker_expected_flag(queue_configured)

    pending_ct = db.exec(
        select(func.count(ClipJobModel.id)).where(ClipJobModel.status == "pending")
    ).one()
    processing_ct = db.exec(
        select(func.count(ClipJobModel.id)).where(ClipJobModel.status == "processing")
    ).one()
    oldest = db.exec(
        select(func.min(ClipJobModel.created_at)).where(ClipJobModel.status == "pending")
    ).one()
    age: int | None = None
    if oldest is not None:
        ts = oldest if oldest.tzinfo else oldest.replace(tzinfo=timezone.utc)
        age = max(0, int((now - ts).total_seconds()))

    return {
        "queue_depth": int(pending_ct or 0),
        "processing_count": int(processing_ct or 0),
        "oldest_pending_age_seconds": age,
        "queue_configured": queue_configured,
        "worker_expected": worker_expected,
    }


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str | bool]:
    """
    Liveness plus whether clip-review providers are configured (no secret values).
    When gemini_configured is false, free-tier jobs may complete with review_method
    provider_unavailable. Pro tier requires twelvelabs_configured unless rollback flag is set.
    """
    settings = get_settings()
    gemini_ok = bool((settings.gemini_api_key or "").strip())
    tl_ok = bool((settings.twelvelabs_api_key or "").strip())
    try:
        db.exec(text("SELECT 1")).one()
    except Exception as err:
        raise HTTPException(status_code=503, detail=f"db_unreachable: {err}") from err
    return {
        "status": "ok",
        "db": "ok",
        "gemini_configured": gemini_ok,
        "twelvelabs_configured": tl_ok,
        "clip_review_ready": gemini_ok and tl_ok,
    }


@router.get("/health/deep")
def health_deep(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    checks = {"db_read": False, "db_write": False, "gemini_configured": False}

    try:
        db.exec(text("SELECT 1")).one()
        checks["db_read"] = True
    except Exception:
        pass

    try:
        # Lightweight write check that works in sqlite/postgres.
        db.exec(text("CREATE TABLE IF NOT EXISTS _healthcheck_tmp (id INTEGER)"))
        db.exec(text("DROP TABLE IF EXISTS _healthcheck_tmp"))
        db.commit()
        checks["db_write"] = True
    except Exception:
        db.rollback()

    checks["gemini_configured"] = bool((settings.gemini_api_key or "").strip())

    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    clip_queue = clip_queue_snapshot(db)
    return {"status": "ok", "checks": checks, "clip_queue": clip_queue}
