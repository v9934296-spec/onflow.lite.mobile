"""P.T.E. Tech 1.0 — What's Next engine tests."""
from __future__ import annotations

import uuid

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
    issue_key: str | None = "timing",
    issue_label: str | None = "Timing",
    session_id: str | None = "sess1",
    job_id: str | None = None,
    best_cue: str | None = "Pop timing is late.",
    best_drill: str | None = "Stationary pop reps",
) -> None:
    jid = job_id or uuid.uuid4().hex[:12]
    s = TrickStatModel(
        user_id=_uid(),
        job_id=jid,
        trick_name=trick,
        landed=landed,
        review_readiness="usable",
        primary_issue_key=issue_key,
        primary_issue_label=issue_label,
        best_cue=best_cue,
        best_drill=best_drill,
        review_method="first_pass_plus_gemini",
        gemini_used=True,
        session_id=session_id,
        technical_limit_summary="Readiness usable.",
    )
    session.add(s)
    session.commit()


def test_whats_next_empty(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/progression/whats-next")
    assert r.status_code == 200
    data = r.json()
    assert data["has_recommendation"] is False
    assert data["focus_trick"] is None
    assert data["confidence"] == "none"


def test_whats_next_single_session(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", issue_key="timing", job_id="w1", session_id="s1")
        _add_stat(session, trick="kickflip", issue_key="timing", job_id="w2", session_id="s1")
        _add_stat(session, trick="heelflip", issue_key="balance", job_id="w3", session_id="s1")
    r = authed_client.get("/api/v1/stats/progression/whats-next")
    data = r.json()
    assert data["has_recommendation"] is True
    assert data["focus_trick"] == "kickflip"
    assert data["focus_issue_key"] == "timing"
    assert data["confidence"] == "moderate"
    assert data["focus_drill"] is not None


def test_whats_next_strong_confidence(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        for i in range(4):
            _add_stat(
                session,
                trick="kickflip",
                issue_key="timing",
                job_id=f"sc{i}",
                session_id="s1",
            )
    r = authed_client.get("/api/v1/stats/progression/whats-next")
    data = r.json()
    assert data["confidence"] == "strong"
    assert data["issue_frequency"] >= 3


def test_whats_next_multiple_sessions(authed_client: TestClient) -> None:
    """Uses last 3 sessions to build recommendation."""
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", issue_key="timing", job_id="ms1", session_id="s1")
        _add_stat(session, trick="kickflip", issue_key="timing", job_id="ms2", session_id="s2")
        _add_stat(session, trick="kickflip", issue_key="balance", job_id="ms3", session_id="s3")
    r = authed_client.get("/api/v1/stats/progression/whats-next")
    data = r.json()
    assert data["has_recommendation"] is True
    assert data["window_sessions"] == 3
    # timing appeared 2x vs balance 1x → timing wins
    assert data["focus_issue_key"] == "timing"


def test_whats_next_no_issues_still_recommends_trick(authed_client: TestClient) -> None:
    """If no issues flagged, still recommends the most-practiced trick."""
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(
            session,
            trick="ollie",
            issue_key=None,
            issue_label=None,
            job_id="ni1",
            session_id="s1",
            best_cue=None,
            best_drill=None,
        )
    r = authed_client.get("/api/v1/stats/progression/whats-next")
    data = r.json()
    assert data["has_recommendation"] is True
    assert data["focus_trick"] == "ollie"
    assert data["focus_issue_key"] is None
    assert data["confidence"] == "emerging"


# ── Session recap upgrade tests ──


def test_session_recap_includes_coaching_recap(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", landed="yes", job_id="sr1", session_id="sess-a")
        _add_stat(session, trick="kickflip", landed="no", job_id="sr2", session_id="sess-a")
        _add_stat(session, trick="heelflip", landed="yes", job_id="sr3", session_id="sess-a")
    r = authed_client.get("/api/v1/stats/sessions/latest")
    assert r.status_code == 200
    data = r.json()
    assert "coaching_recap" in data
    assert len(data["coaching_recap"]) == 2
    # kickflip has more attempts so should be first
    assert data["coaching_recap"][0]["trick_name"] == "kickflip"
    assert data["coaching_recap"][0]["attempts"] == 2
    assert data["coaching_recap"][0]["makes"] == 1


def test_session_recap_includes_focus(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", issue_key="timing", job_id="sf1", session_id="sess-b")
        _add_stat(session, trick="kickflip", issue_key="timing", job_id="sf2", session_id="sess-b")
    r = authed_client.get("/api/v1/stats/sessions/latest")
    data = r.json()
    assert "focus_for_next_session" in data
    assert data["focus_for_next_session"]["issue_key"] == "timing"
    assert data["focus_for_next_session"]["occurrences"] == 2


def test_session_empty_has_new_fields(authed_client: TestClient) -> None:
    r = authed_client.get("/api/v1/stats/sessions/latest")
    data = r.json()
    assert data["coaching_recap"] == []
    assert data["focus_for_next_session"] is None
    assert data.get("session_recap") is None


def test_session_payload_includes_structured_session_recap(authed_client: TestClient) -> None:
    engine = get_engine()
    with Session(engine) as session:
        _add_stat(session, trick="kickflip", landed="no", job_id="srx1", session_id="sess-x")
        _add_stat(session, trick="kickflip", landed="yes", job_id="srx2", session_id="sess-x")
    r = authed_client.get("/api/v1/stats/sessions/latest")
    data = r.json()
    recap = data.get("session_recap")
    assert isinstance(recap, dict)
    assert recap["recap_available"] is True
    assert recap["session_id"] == "sess-x"
    assert recap["session_attempt_count"] == 2
    assert recap["session_summary"]
    assert recap["next_session_focus"]
