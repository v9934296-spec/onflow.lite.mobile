"""Progression timeline endpoint (Step 5F) — a skater's personal session history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.schemas.progression import ProgressionTimelineResponse
from app.schemas.trick_compare import TrickClipCompareResponse
from app.services.progression_timeline import list_progression_timeline
from app.services.trick_clip_compare import build_trick_clip_compare

router = APIRouter(prefix="/api/v1", tags=["progression"])


@router.get("/progression/timeline", response_model=ProgressionTimelineResponse)
def get_progression_timeline(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> ProgressionTimelineResponse:
    """Owner-scoped, newest-first history of the user's completed sessions.

    Offset pagination (``page``/``page_size``); lightweight session previews only.
    """
    items, has_more = list_progression_timeline(
        db, user_id, page=page, page_size=page_size
    )
    return ProgressionTimelineResponse(
        items=items,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get(
    "/progression/tricks/{trick_name}/compare",
    response_model=TrickClipCompareResponse,
)
def get_trick_clip_compare(
    trick_name: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrickClipCompareResponse:
    """Owner-scoped oldest-vs-newest clip comparison for one trick (Step 5G)."""
    result = build_trick_clip_compare(db, user_id, trick_name)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No analyzed clips found for trick '{trick_name}'.",
        )
    return result
