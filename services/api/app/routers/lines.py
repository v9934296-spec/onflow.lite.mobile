"""P.T.E. Tech 1.0 — Custom line definitions and attempt tracking."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models import CustomLineModel, LineAttemptModel
from app.services.session_grouping import resolve_session_id

router = APIRouter(prefix="/api/v1/lines", tags=["lines"])

MAX_LINES_PER_USER = 20
MAX_TRICKS_PER_LINE = 4

# Lazy-seeded on first list when a user has no lines (onboarding).
_SEED_LINE_NAME = "Example: ollie → kickflip"
_SEED_TRICKS = ["ollie", "kickflip"]


class CreateLineRequest(BaseModel):
    line_name: str = Field(min_length=1, max_length=100)
    trick_sequence: list[str] = Field(min_length=2, max_length=4)


class UpdateLineRequest(BaseModel):
    line_name: str | None = Field(default=None, min_length=1, max_length=100)
    trick_sequence: list[str] | None = Field(default=None, min_length=2, max_length=4)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat().replace("+00:00", "Z")


def _line_to_dict(
    line: CustomLineModel, attempts: list[LineAttemptModel] | None = None
) -> dict[str, Any]:
    att_list = attempts or []
    total = len(att_list)
    landed = sum(1 for a in att_list if a.landed == "yes")
    return {
        "line_id": line.id,
        "line_name": line.line_name,
        "trick_sequence": line.trick_sequence,
        "total_attempts": total,
        "landed": landed,
        "percentage": round((landed / total * 100) if total else 0, 1),
        "created_at": _iso(line.created_at),
        "updated_at": _iso(line.updated_at),
    }


@router.post("")
def create_line(
    body: CreateLineRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a custom line definition."""
    stmt = select(CustomLineModel).where(CustomLineModel.user_id == user_id)
    existing = list(db.exec(stmt))
    if len(existing) >= MAX_LINES_PER_USER:
        raise HTTPException(
            status_code=400, detail=f"Max {MAX_LINES_PER_USER} lines per user."
        )

    clean_seq = [t.strip().lower() for t in body.trick_sequence if t.strip()]
    if len(clean_seq) < 2:
        raise HTTPException(status_code=400, detail="A line needs at least 2 tricks.")

    line = CustomLineModel(
        user_id=user_id,
        line_name=body.line_name.strip(),
        trick_sequence_json=json.dumps(clean_seq),
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return _line_to_dict(line)


@router.get("")
def list_lines(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all custom lines with attempt stats."""
    stmt = (
        select(CustomLineModel)
        .where(CustomLineModel.user_id == user_id)
        .order_by(CustomLineModel.created_at.desc())
    )
    lines = list(db.exec(stmt))
    if not lines:
        seed = CustomLineModel(
            user_id=user_id,
            line_name=_SEED_LINE_NAME,
            trick_sequence_json=json.dumps(_SEED_TRICKS),
        )
        db.add(seed)
        db.commit()
        lines = list(db.exec(stmt))

    result = []
    for line in lines:
        att_stmt = select(LineAttemptModel).where(
            LineAttemptModel.user_id == user_id,
            LineAttemptModel.line_id == line.id,
        )
        attempts = list(db.exec(att_stmt))
        result.append(_line_to_dict(line, attempts))
    return result


@router.get("/{line_id}")
def get_line(
    line_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get a single line with full attempt history."""
    line = db.exec(
        select(CustomLineModel).where(
            CustomLineModel.id == line_id,
            CustomLineModel.user_id == user_id,
        )
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="Line not found.")

    att_stmt = (
        select(LineAttemptModel)
        .where(
            LineAttemptModel.line_id == line_id,
            LineAttemptModel.user_id == user_id,
        )
        .order_by(LineAttemptModel.created_at.desc())
    )
    attempts = list(db.exec(att_stmt))

    d = _line_to_dict(line, attempts)
    d["attempts"] = [
        {
            "attempt_id": a.id,
            "job_id": a.job_id,
            "landed": a.landed,
            "session_id": a.session_id,
            "created_at": _iso(a.created_at),
        }
        for a in attempts
    ]
    return d


@router.put("/{line_id}")
def update_line(
    line_id: str,
    body: UpdateLineRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update a line's name or trick sequence."""
    line = db.exec(
        select(CustomLineModel).where(
            CustomLineModel.id == line_id,
            CustomLineModel.user_id == user_id,
        )
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="Line not found.")

    if body.line_name is not None:
        line.line_name = body.line_name.strip()
    if body.trick_sequence is not None:
        clean_seq = [t.strip().lower() for t in body.trick_sequence if t.strip()]
        if len(clean_seq) < 2:
            raise HTTPException(status_code=400, detail="A line needs at least 2 tricks.")
        line.trick_sequence_json = json.dumps(clean_seq)

    line.updated_at = datetime.now(timezone.utc)
    db.add(line)
    db.commit()
    db.refresh(line)
    att_stmt = select(LineAttemptModel).where(
        LineAttemptModel.user_id == user_id,
        LineAttemptModel.line_id == line.id,
    )
    attempts = list(db.exec(att_stmt))
    return _line_to_dict(line, attempts)


@router.delete("/{line_id}")
def delete_line(
    line_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete a line and all its attempts."""
    line = db.exec(
        select(CustomLineModel).where(
            CustomLineModel.id == line_id,
            CustomLineModel.user_id == user_id,
        )
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="Line not found.")

    att_stmt = select(LineAttemptModel).where(
        LineAttemptModel.line_id == line_id,
        LineAttemptModel.user_id == user_id,
    )
    for a in db.exec(att_stmt):
        db.delete(a)
    db.delete(line)
    db.commit()
    return {"status": "deleted", "line_id": line_id}


@router.post("/{line_id}/attempts")
def record_line_attempt(
    line_id: str,
    job_id: str = Query(..., min_length=1),
    landed: str = Query("unclear"),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record an attempt of a custom line."""
    line = db.exec(
        select(CustomLineModel).where(
            CustomLineModel.id == line_id,
            CustomLineModel.user_id == user_id,
        )
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="Line not found.")

    landed_clean = landed if landed in ("yes", "no") else None

    sid = resolve_session_id(db, user_id)

    attempt = LineAttemptModel(
        user_id=user_id,
        line_id=line_id,
        job_id=job_id,
        landed=landed_clean,
        session_id=sid,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return {
        "attempt_id": attempt.id,
        "line_id": line_id,
        "job_id": job_id,
        "landed": attempt.landed,
        "session_id": attempt.session_id,
        "created_at": _iso(attempt.created_at),
    }
