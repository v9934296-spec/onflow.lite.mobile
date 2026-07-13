"""P.T.E. Tech 1.0 — Milestone system tests."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import TrickStatModel
from app.services.milestones import check_milestones


def _uid() -> str:
    return "test-user-001"


def _add_stat(
    session: Session,
    *,
    trick: str = "kickflip",
    landed: str | None = "yes",
    session_id: str | None = "sess1",
    job_id: str | None = None,
) -> TrickStatModel:
    jid = job_id or uuid.uuid4().hex[:12]
    s = TrickStatModel(
        user_id=_uid(),
        job_id=jid,
        trick_name=trick,
        landed=landed,
        review_readiness="usable",
        primary_issue_key="timing",
        primary_issue_label="Timing",
        best_cue="Front foot lifts early.",
        best_drill="Stationary pop reps",
        review_method="first_pass_plus_gemini",
        gemini_used=True,
        session_id=session_id,
        technical_limit_summary="Readiness usable.",
    )
    session.add(s)
    session.flush()
    return s


# ── new_trick ──


def test_new_trick_milestone(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", job_id="j1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="j1",
            trick_name="kickflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    assert r.status_code == 200
    keys = [m["milestone_key"] for m in r.json()]
    assert "new_trick" in keys


def test_new_trick_not_duplicated(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", job_id="j1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="j1",
            trick_name="kickflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        _add_stat(session, trick="kickflip", job_id="j2")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="j2",
            trick_name="kickflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    new_trick_entries = [
        m for m in r.json() if m["milestone_key"] == "new_trick" and m["trick_name"] == "kickflip"
    ]
    assert len(new_trick_entries) == 1


# ── first_make ──


def test_first_make_on_landed(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="heelflip", landed="yes", job_id="j1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="j1",
            trick_name="heelflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    keys = [m["milestone_key"] for m in r.json()]
    assert "first_make" in keys


def test_first_make_not_on_bail(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="heelflip", landed="no", job_id="j1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="j1",
            trick_name="heelflip",
            landed="no",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    keys = [m["milestone_key"] for m in r.json()]
    assert "first_make" not in keys


# ── locked_in (3 consecutive in session) ──


def test_locked_in_after_3_consecutive(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        for i in range(3):
            _add_stat(session, trick="kickflip", landed="yes", job_id=f"li{i}", session_id="sess1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="li2",
            trick_name="kickflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    keys = [m["milestone_key"] for m in r.json()]
    assert "locked_in" in keys


def test_locked_in_broken_by_bail(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", landed="yes", job_id="a1", session_id="sess1")
        _add_stat(session, trick="kickflip", landed="no", job_id="a2", session_id="sess1")
        _add_stat(session, trick="kickflip", landed="yes", job_id="a3", session_id="sess1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="a3",
            trick_name="kickflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    locked = [m for m in r.json() if m["milestone_key"] == "locked_in"]
    assert len(locked) == 0


# ── dialed (5 consecutive any sessions) ──


def test_dialed_after_5_consecutive(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        for i in range(5):
            sid = f"sess{i // 3 + 1}"
            _add_stat(session, trick="kickflip", landed="yes", job_id=f"d{i}", session_id=sid)
        check_milestones(
            session,
            user_id=_uid(),
            job_id="d4",
            trick_name="kickflip",
            landed="yes",
            session_id="sess2",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    keys = [m["milestone_key"] for m in r.json()]
    assert "dialed" in keys


# ── session_grind (5+ clips in one session) ──


def test_session_grind_after_5_clips(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        for i in range(5):
            _add_stat(session, trick=f"trick{i}", landed="yes", job_id=f"sg{i}", session_id="sess1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="sg4",
            trick_name="trick4",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    keys = [m["milestone_key"] for m in r.json()]
    assert "session_grind" in keys


# ── line_landed (2+ tricks, landed) ──


def test_line_landed_multi_trick_clip(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", landed="yes", job_id="ll1", session_id="sess1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="ll1",
            trick_name="kickflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=2,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    keys = [m["milestone_key"] for m in r.json()]
    assert "line_landed" in keys


def test_line_landed_not_on_single_trick(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", landed="yes", job_id="ll2", session_id="sess1")
        check_milestones(
            session,
            user_id=_uid(),
            job_id="ll2",
            trick_name="kickflip",
            landed="yes",
            session_id="sess1",
            tricks_in_clip=1,
        )
        session.commit()
    r = authed_client.get("/api/v1/stats/milestones")
    line_entries = [m for m in r.json() if m["milestone_key"] == "line_landed"]
    assert len(line_entries) == 0


# ── milestones endpoint empty ──


def test_milestones_empty(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/milestones")
    assert r.status_code == 200
    assert r.json() == []
