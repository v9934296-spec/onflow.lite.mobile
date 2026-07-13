"""Per-trick stats, session summaries."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import MilestoneModel, TrickStatModel
from app.services.progression_overview import build_progression_overview
from app.services.whats_next import build_whats_next
from app.services.stats_logic import (
    build_session_payload,
    build_trick_progression,
    attempt_to_dict,
)

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


def _rows_for_trick(user_id: str, trick_name: str, db: Session) -> list[TrickStatModel]:
    clean = trick_name.strip().lower()
    stmt = (
        select(TrickStatModel)
        .where(
            TrickStatModel.user_id == user_id,
            TrickStatModel.trick_name == clean,
        )
        .order_by(TrickStatModel.created_at.desc())
    )
    return list(db.exec(stmt))


@router.get("/progression/overview")
def get_progression_overview(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """P.T.E. Tech 1.0 — full progression snapshot for dashboard."""
    stmt = select(TrickStatModel).where(TrickStatModel.user_id == user_id)
    rows = list(db.exec(stmt))
    return build_progression_overview(rows)


MILESTONE_DISPLAY_NAMES: dict[str, str] = {
    "first_make": "First Make",
    "locked_in": "Locked In",
    "dialed": "Dialed",
    "new_trick": "New Trick",
    "session_grind": "Session Grind",
    "line_landed": "Line Landed",
}


@router.get("/milestones")
def get_milestones(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """P.T.E. Tech 1.0 — all milestones unlocked by this user."""
    stmt = (
        select(MilestoneModel)
        .where(MilestoneModel.user_id == user_id)
        .order_by(MilestoneModel.achieved_at.desc())
    )
    rows = list(db.exec(stmt))
    return [
        {
            "milestone_key": r.milestone_key,
            "name": MILESTONE_DISPLAY_NAMES.get(r.milestone_key, r.milestone_key),
            "trick_name": r.trick_name,
            "session_id": r.session_id,
            "job_id": r.job_id,
            "achieved_at": r.achieved_at.isoformat() + "Z"
            if r.achieved_at.tzinfo is None
            else r.achieved_at.isoformat().replace("+00:00", "Z"),
        }
        for r in rows
    ]


@router.get("/progression/whats-next")
def get_whats_next(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """P.T.E. Tech 1.0 — single focus recommendation from recent Gemini coaching."""
    stmt = (
        select(TrickStatModel)
        .where(TrickStatModel.user_id == user_id)
        .order_by(TrickStatModel.created_at.desc())
    )
    rows = list(db.exec(stmt))
    return build_whats_next(rows)


@router.get("/tricks")
def get_trick_stats(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(TrickStatModel)
        .where(TrickStatModel.user_id == user_id)
        .order_by(TrickStatModel.created_at.desc())
    )
    rows = list(db.exec(stmt))

    by_trick: dict[str, dict[str, Any]] = {}
    buckets: dict[str, list[TrickStatModel]] = defaultdict(list)
    for row in rows:
        buckets[row.trick_name].append(row)
    for name in buckets:
        buckets[name].sort(key=lambda r: r.created_at, reverse=True)

    for row in rows:
        name = row.trick_name
        if name not in by_trick:
            by_trick[name] = {
                "trick_name": name,
                "attempts": 0,
                "makes": 0,
                "last_attempted": row.created_at.isoformat(),
                "best_readiness": row.review_readiness,
            }
        entry = by_trick[name]
        entry["attempts"] += 1
        if row.landed == "yes":
            entry["makes"] += 1
        readiness_rank = {"usable": 3, "limited": 2, "insufficient": 1}
        if readiness_rank.get(row.review_readiness, 0) > readiness_rank.get(
            entry["best_readiness"], 0
        ):
            entry["best_readiness"] = row.review_readiness

    for name, entry in by_trick.items():
        trows = buckets[name]
        keys = [r.primary_issue_key for r in trows if r.primary_issue_key]
        dom = Counter(keys).most_common(1)
        entry["dominant_issue_key"] = dom[0][0] if dom else None
        labels = {r.primary_issue_key: r.primary_issue_label for r in trows if r.primary_issue_key}
        entry["dominant_issue_label"] = labels.get(entry["dominant_issue_key"]) if entry["dominant_issue_key"] else None
        entry["latest_best_cue"] = trows[0].best_cue if trows else None
        last5 = trows[:5]
        mk = sum(1 for r in last5 if r.landed == "yes")
        entry["trend_last_5_make_rate"] = round((mk / len(last5) * 100) if last5 else 0, 1)
        entry["percentage"] = round(
            (entry["makes"] / entry["attempts"] * 100) if entry["attempts"] > 0 else 0,
            1,
        )

    result = list(by_trick.values())
    result.sort(key=lambda x: x["last_attempted"], reverse=True)
    return result


@router.get("/tricks/{trick_name}")
def get_trick_detail(
    trick_name: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    clean_name = trick_name.strip().lower()
    rows = _rows_for_trick(user_id, clean_name, db)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No stats found for trick '{trick_name}'.",
        )

    attempts = []
    makes = 0
    for row in rows:
        attempts.append(attempt_to_dict(row))
        if row.landed == "yes":
            makes += 1

    return {
        "trick_name": clean_name,
        "total_attempts": len(attempts),
        "makes": makes,
        "percentage": round((makes / len(attempts) * 100) if attempts else 0, 1),
        "attempts": attempts,
    }


@router.get("/tricks/{trick_name}/progression")
def get_trick_progression(
    trick_name: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """P.T.E. Tech 1.0 — merged trick detail + compare + coaching timeline."""
    clean = trick_name.strip().lower()
    rows = _rows_for_trick(user_id, clean, db)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No stats for '{trick_name}'.")
    return build_trick_progression(rows, clean)


@router.get("/sessions/latest")
def get_latest_session(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = (
        select(TrickStatModel)
        .where(TrickStatModel.user_id == user_id)
        .order_by(TrickStatModel.created_at.desc())
        .limit(1)
    )
    latest = db.exec(stmt).first()
    if not latest:
        return build_session_payload("", [])
    if latest.session_id:
        sid = latest.session_id
        stmt2 = select(TrickStatModel).where(
            TrickStatModel.user_id == user_id,
            TrickStatModel.session_id == sid,
        )
        rows = list(db.exec(stmt2))
        return build_session_payload(sid, rows)
    # Legacy rows without session_id: group same UTC calendar day as latest attempt
    d = latest.created_at.date()
    stmt_all = select(TrickStatModel).where(TrickStatModel.user_id == user_id)
    rows = [r for r in db.exec(stmt_all) if r.created_at.date() == d]
    return build_session_payload(f"day-{d.isoformat()}", rows)


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(TrickStatModel).where(
        TrickStatModel.user_id == user_id,
        TrickStatModel.session_id == session_id,
    )
    rows = list(db.exec(stmt))
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found.")
    return build_session_payload(session_id, rows)
