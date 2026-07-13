"""GET /api/v1/progression/tricks/{trick}/compare — Step 5G clip comparison."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import ClipModel, SkateSessionModel, TrickStatModel

BASE = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _session(user_id: str) -> str:
    sid = str(uuid.uuid4())
    with Session(get_engine()) as db:
        db.add(
            SkateSessionModel(
                id=sid,
                user_id=user_id,
                started_at=BASE,
                ended_at=BASE + timedelta(hours=1),
            )
        )
        db.commit()
    return sid


def _clip(
    user_id: str,
    session_id: str,
    *,
    trick: str,
    created: datetime,
    pte: int | None = None,
    landed: bool | None = None,
    with_stat: bool = False,
) -> str:
    cid = str(uuid.uuid4())
    with Session(get_engine()) as db:
        db.add(
            ClipModel(
                id=cid,
                user_id=user_id,
                session_id=session_id,
                trick_id=trick,
                storage_key=f"clips/{cid}.mp4",
                storage_url=f"https://cdn/{cid}.mp4",
                thumbnail_url=f"https://cdn/{cid}.jpg",
                upload_status="analyzed",
                pte_rating=pte,
                landed=landed,
                created_at=created,
            )
        )
        if with_stat:
            db.add(
                TrickStatModel(
                    user_id=user_id,
                    job_id=cid,
                    trick_name=trick,
                    landed="yes" if landed else "no" if landed is False else None,
                    review_readiness="usable" if landed else "limited",
                    best_cue="Pop straight down" if landed else "Commit shoulders",
                    primary_issue_key="timing" if not landed else "commitment",
                    primary_issue_label="Timing" if not landed else "Commitment",
                )
            )
        db.commit()
    return cid


def test_owner_scoped_404_for_other_user_trick(authed_client: TestClient) -> None:
    sid = _session("other-user-xyz")
    _clip("other-user-xyz", sid, trick="kickflip", created=BASE, pte=5)
    r = authed_client.get("/api/v1/progression/tricks/kickflip/compare")
    assert r.status_code == 404


def test_single_clip_compare_not_available(authed_client: TestClient) -> None:
    sid = _session("test-user-001")
    _clip("test-user-001", sid, trick="kickflip", created=BASE, pte=6, landed=False)
    body = authed_client.get("/api/v1/progression/tricks/kickflip/compare").json()
    assert body["compare_available"] is False
    assert body["clips_count"] == 1
    assert body["newest_clip"]["pte_score"] == 6


def test_oldest_newest_with_deltas(authed_client: TestClient) -> None:
    sid = _session("test-user-001")
    _clip(
        "test-user-001",
        sid,
        trick="kickflip",
        created=BASE,
        pte=5,
        landed=False,
        with_stat=True,
    )
    _clip(
        "test-user-001",
        sid,
        trick="kickflip",
        created=BASE + timedelta(days=92),
        pte=8,
        landed=True,
        with_stat=True,
    )
    body = authed_client.get("/api/v1/progression/tricks/kickflip/compare").json()
    assert body["compare_available"] is True
    assert body["days_between"] == 92
    assert body["pte_delta"] == 3
    assert body["oldest_clip"]["pte_score"] == 5
    assert body["newest_clip"]["pte_score"] == 8
    assert body["oldest_landed"] is False
    assert body["newest_landed"] is True
    assert len(body["progress_notes"]) >= 1


def test_missing_trick_returns_404(authed_client: TestClient) -> None:
    assert authed_client.get("/api/v1/progression/tricks/unknown-trick-xyz/compare").status_code == 404
