"""Stats compare + session summary routes."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import TrickStatModel


def _uid() -> str:
    return "test-user-001"


def _add_stat(
    session: Session,
    *,
    trick: str = "kickflip",
    landed: str | None = "yes",
    readiness: str = "usable",
    issue_key: str | None = "timing",
    issue_label: str | None = "Timing",
    session_id: str | None = "sess1",
    job_id: str | None = None,
    land_score: float | None = None,
) -> None:
    jid = job_id or uuid.uuid4().hex[:12]
    s = TrickStatModel(
        user_id=_uid(),
        job_id=jid,
        trick_name=trick,
        landed=landed,
        review_readiness=readiness,
        primary_issue_key=issue_key,
        primary_issue_label=issue_label,
        best_cue="Front foot lifts early during flick.",
        best_drill="Stationary pop reps",
        review_method="first_pass_plus_gemini",
        gemini_used=True,
        session_id=session_id,
        technical_limit_summary="Readiness usable.",
        land_score=land_score,
    )
    session.add(s)
    session.commit()


def test_compare_404_when_no_trick_stats(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/tricks/kickflip/progression")
    assert r.status_code == 404


def test_compare_available_false_with_one_attempt(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, job_id="a1")
    r = authed_client.get("/api/v1/stats/tricks/kickflip/progression")
    assert r.status_code == 200
    data = r.json()["compare"]
    assert data["compare_available"] is False
    assert data["trend"]["last_5_landed_yes"] == 0


def test_compare_two_attempts(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, job_id="j2", landed="no", issue_key="timing")
        _add_stat(session, job_id="j1", landed="yes", issue_key="timing")
    r = authed_client.get("/api/v1/stats/tricks/kickflip/progression")
    assert r.status_code == 200
    data = r.json()["compare"]
    assert data["compare_available"] is True
    assert data["latest_attempt"]["job_id"] == "j1"
    assert data["baseline_window_count"] >= 1


def test_trick_list_includes_progression_fields(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, job_id="x1")
    r = authed_client.get("/api/v1/stats/tricks")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert "dominant_issue_key" in rows[0]
    assert "latest_best_cue" in rows[0]
    assert "trend_last_5_make_rate" in rows[0]


def test_sessions_latest_empty(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/sessions/latest")
    assert r.status_code == 200
    data = r.json()
    assert data["total_attempts"] == 0


def test_sessions_latest_with_data(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, job_id="s1", session_id="sess-a")
    r = authed_client.get("/api/v1/stats/sessions/latest")
    assert r.status_code == 200
    assert r.json()["session_id"] == "sess-a"
    assert r.json()["total_attempts"] == 1


def test_session_detail_404(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/sessions/does-not-exist")
    assert r.status_code == 404


# ── P.T.E. Tech 1.0: Progression Overview ──


def test_progression_overview_empty(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/progression/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["total_attempts"] == 0
    assert data["total_sessions"] == 0
    assert data["global_make_rate"] == 0.0
    assert data["top_5_tricks"] == []
    assert data["recent_activity"] == []
    assert data["current_streak"] == 0
    assert data["longest_streak"] == 0


def test_progression_overview_basic(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", landed="yes", job_id="p1", session_id="s1")
        _add_stat(session, trick="kickflip", landed="no", job_id="p2", session_id="s1")
        _add_stat(session, trick="heelflip", landed="yes", job_id="p3", session_id="s1")
    r = authed_client.get("/api/v1/stats/progression/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["total_attempts"] == 3
    assert data["total_makes"] == 2
    assert data["global_make_rate"] == 66.7
    assert data["total_sessions"] == 1
    assert data["total_tricks_attempted"] == 2
    assert len(data["top_5_tricks"]) == 2
    # kickflip has more attempts so should be first
    assert data["top_5_tricks"][0]["trick_name"] == "kickflip"
    assert data["top_5_tricks"][0]["attempts"] == 2
    assert len(data["recent_activity"]) == 3


def test_progression_overview_top5_capped(authed_client: TestClient) -> None:
    """If user has > 5 tricks, only top 5 by attempts are returned."""
    engine = get_engine()
    with Session(engine) as session:
        for i, trick in enumerate(
            ["ollie", "kickflip", "heelflip", "treflip", "hardflip", "varial"],
        ):
            for j in range(6 - i):  # ollie=6, kickflip=5, ..., varial=1
                _add_stat(session, trick=trick, landed="yes", job_id=f"t{i}-{j}", session_id="s1")
    r = authed_client.get("/api/v1/stats/progression/overview")
    data = r.json()
    assert len(data["top_5_tricks"]) == 5
    assert data["top_5_tricks"][0]["trick_name"] == "ollie"
    # varial (1 attempt) should NOT be in top 5
    names = [t["trick_name"] for t in data["top_5_tricks"]]
    assert "varial" not in names


def test_progression_overview_recent_activity_limit(authed_client: TestClient) -> None:
    """Recent activity is capped at 10 entries."""
    engine = get_engine()
    with Session(engine) as session:
        for i in range(15):
            _add_stat(session, trick="kickflip", landed="yes", job_id=f"r{i}", session_id="s1")
    r = authed_client.get("/api/v1/stats/progression/overview")
    data = r.json()
    assert len(data["recent_activity"]) == 10


def test_progression_overview_best_land_score_landed_only(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(
            session,
            trick="heelflip",
            landed="yes",
            land_score=7.0,
            job_id="land-y-7",
            session_id="s1",
        )
        _add_stat(
            session,
            trick="heelflip",
            landed="no",
            land_score=9.0,
            job_id="land-n-9",
            session_id="s1",
        )
        _add_stat(
            session,
            trick="heelflip",
            landed="yes",
            land_score=6.0,
            job_id="land-y-6",
            session_id="s1",
        )
    r = authed_client.get("/api/v1/stats/progression/overview")
    assert r.status_code == 200
    data = r.json()
    heelflip = next(t for t in data["top_5_tricks"] if t["trick_name"] == "heelflip")
    assert heelflip["best_land_score"] == 7.0
    assert heelflip["best_land_job_id"] == "land-y-7"


def test_progression_overview_best_land_score_none_without_landed(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(
            session,
            trick="kickflip",
            landed="no",
            job_id="nol-1",
            session_id="s1",
        )
        _add_stat(
            session,
            trick="kickflip",
            landed=None,
            job_id="nol-2",
            session_id="s1",
        )
    r = authed_client.get("/api/v1/stats/progression/overview")
    assert r.status_code == 200
    data = r.json()
    kickflip = next(t for t in data["top_5_tricks"] if t["trick_name"] == "kickflip")
    assert kickflip["best_land_score"] is None
    assert kickflip["best_land_job_id"] is None


def test_progression_overview_best_land_score_max_and_tie_break_recent(
    authed_client: TestClient,
) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(
            session,
            trick="ollie",
            landed="yes",
            land_score=8.5,
            job_id="old-best",
            session_id="s1",
        )
        _add_stat(
            session,
            trick="ollie",
            landed="yes",
            land_score=8.5,
            job_id="new-best",
            session_id="s1",
        )
    r = authed_client.get("/api/v1/stats/progression/overview")
    assert r.status_code == 200
    data = r.json()
    ollie = next(t for t in data["top_5_tricks"] if t["trick_name"] == "ollie")
    assert ollie["best_land_score"] == 8.5
    assert ollie["best_land_job_id"] == "new-best"


# ── P.T.E. Tech 1.0: Trick Progression (merged) ──


def test_trick_progression_404(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/tricks/kickflip/progression")
    assert r.status_code == 404


def test_trick_progression_merged(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", landed="yes", job_id="tp1", issue_key="timing")
        _add_stat(session, trick="kickflip", landed="no", job_id="tp2", issue_key="balance")
        _add_stat(session, trick="kickflip", landed="yes", job_id="tp3", issue_key="timing")
    r = authed_client.get("/api/v1/stats/tricks/kickflip/progression")
    assert r.status_code == 200
    data = r.json()
    assert data["total_attempts"] == 3
    assert data["makes"] == 2
    assert "compare" in data
    assert data["compare"]["trick_name"] == "kickflip"
    assert "coaching_timeline" in data
    assert len(data["coaching_timeline"]) == 3
    assert data["coaching_timeline"][0]["primary_issue_key"] is not None
