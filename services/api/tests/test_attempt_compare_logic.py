"""Unit tests for attempt_compare block (latest vs up to 3 priors)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models import TrickStatModel
from app.services.stats_logic import (
    build_attempt_compare_block,
    build_compare_payload,
    fetch_prior_trick_stats,
)


def _row(
    *,
    job_id: str,
    landed: str | None = "yes",
    readiness: str = "usable",
    issue_key: str | None = "timing",
    issue_label: str | None = "Timing",
) -> TrickStatModel:
    return TrickStatModel(
        user_id="u1",
        job_id=job_id,
        trick_name="kickflip",
        landed=landed,
        review_readiness=readiness,
        primary_issue_key=issue_key,
        primary_issue_label=issue_label,
        best_cue="Cue",
        best_drill="Drill",
        review_method="first_pass_plus_gemini",
        gemini_used=True,
        created_at=datetime.now(timezone.utc),
    )


def test_build_attempt_compare_returns_none_without_priors() -> None:
    out = build_attempt_compare_block(
        trick_display_name="Kickflip",
        trick_name_normalized="kickflip",
        job_id="new1",
        latest_result={
            "review_readiness": "usable",
            "landed": "yes",
            "primary_issue_key": "timing",
            "primary_issue_label": "Timing",
        },
        latest_created_at_iso="2026-04-19T12:00:00Z",
        previous_rows=[],
    )
    assert out is None


def test_build_attempt_compare_with_one_prior() -> None:
    prev = [_row(job_id="p1", readiness="limited", landed="no")]
    out = build_attempt_compare_block(
        trick_display_name="Kickflip",
        trick_name_normalized="kickflip",
        job_id="new1",
        latest_result={
            "review_readiness": "usable",
            "landed": "yes",
            "primary_issue_key": "timing",
            "primary_issue_label": "Timing",
            "best_cue": "Stay centered",
        },
        latest_created_at_iso="2026-04-19T12:00:00Z",
        previous_rows=prev,
    )
    assert out is not None
    assert out["compare_available"] is True
    assert out["baseline_window_count"] == 1
    assert len(out["previous_attempts"]) == 1
    assert "thin" in out["compare_summary"].lower()
    assert out["best_next_focus"]


def test_compare_payload_uses_three_prior_window() -> None:
    rows = [
        _row(job_id="n", landed="yes"),
        _row(job_id="a", landed="no"),
        _row(job_id="b", landed="yes"),
        _row(job_id="c", landed="no"),
        _row(job_id="d", landed="yes"),
    ]
    data = build_compare_payload(rows, "kickflip")
    assert data["baseline_window_count"] == 3
    assert data["compare_available"] is True


def test_fetch_prior_respects_exclude_job() -> None:
    """Integration-style: prior fetch excludes current job id."""
    from sqlmodel import Session

    from app.core.database import get_engine

    uid = f"fetch-{uuid.uuid4().hex[:8]}"
    eng = get_engine()
    jid_a = uuid.uuid4().hex[:12]
    jid_b = uuid.uuid4().hex[:12]
    with Session(eng) as session:
        session.add(
            TrickStatModel(
                user_id=uid,
                job_id=jid_a,
                trick_name="kickflip",
                landed="yes",
                review_readiness="usable",
                primary_issue_key="t",
                primary_issue_label="T",
                review_method="x",
                gemini_used=False,
            )
        )
        session.add(
            TrickStatModel(
                user_id=uid,
                job_id=jid_b,
                trick_name="kickflip",
                landed="no",
                review_readiness="limited",
                primary_issue_key="t",
                primary_issue_label="T",
                review_method="x",
                gemini_used=False,
            )
        )
        session.commit()

    with Session(eng) as session:
        pri = fetch_prior_trick_stats(session, uid, "kickflip", jid_b, limit=3)
    assert len(pri) == 1
    assert pri[0].job_id == jid_a
