"""Reap abandoned V1 pending clip uploads (no complete-upload)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine
from app.models import ClipModel
from app.services.object_storage import ObjectStorage, build_storage

logger = structlog.get_logger(__name__)


async def reap_abandoned_pending_clips(
    *,
    storage: ObjectStorage | None = None,
    older_than_hours: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """
    Delete object storage + DB rows for V1 clips stuck in ``pending`` longer
    than the configured window. Does not touch analyzing/analyzed clips.
    """
    settings = get_settings()
    hours = older_than_hours
    if hours is None:
        hours = max(1, int(getattr(settings, "clip_pending_reap_hours", 24) or 24))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    store = storage or build_storage()

    deleted_rows = 0
    deleted_objects = 0
    errors = 0

    with Session(get_engine()) as session:
        stmt = (
            select(ClipModel)
            .where(
                ClipModel.upload_status == "pending",
                ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
                ClipModel.created_at < cutoff,
            )
            .order_by(ClipModel.created_at.asc())
            .limit(max(1, limit))
        )
        rows = list(session.exec(stmt))

    for row in rows:
        key = (row.storage_key or "").strip()
        thumb = (row.thumbnail_key or "").strip() if row.thumbnail_key else ""
        for k in (key, thumb):
            if not k:
                continue
            try:
                await store.delete(k)
                deleted_objects += 1
            except Exception:
                errors += 1
                logger.warning(
                    "pending_reaper_storage_delete_failed",
                    clip_id=row.id,
                    key=k,
                    exc_info=True,
                )
        try:
            with Session(get_engine()) as session:
                m = session.get(ClipModel, row.id)
                if m is not None and m.upload_status == "pending":
                    session.delete(m)
                    session.commit()
                    deleted_rows += 1
        except Exception:
            errors += 1
            logger.warning(
                "pending_reaper_row_delete_failed",
                clip_id=row.id,
                exc_info=True,
            )

    report = {
        "scanned": len(rows),
        "deleted_rows": deleted_rows,
        "deleted_objects": deleted_objects,
        "errors": errors,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "older_than_hours": hours,
    }
    logger.info("pending_reaper_complete", **report)
    return report
