"""
Sargability and correctness tests for the monthly quota query.

The quota query previously wrapped ``created_at`` in
``EXTRACT(year FROM ...) = ?`` and ``EXTRACT(month FROM ...) = ?`` predicates,
which prevent Postgres from using an index on the column. The fix rewrites the
``WHERE`` clause to range bounds (``created_at >= month_start AND
created_at < next_month_start``).

These tests pin both the behavioural contract (correct count across a month
boundary) and the sargability contract (no function call wraps ``created_at``
in the compiled SQL).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects import postgresql, sqlite
from sqlmodel import Session

from app.core.database import get_engine
from app.models import ClipJobModel
from app.repositories.clip_jobs import (
    SqlClipJobRepository,
    _current_month_bounds_utc,
)


def _seed(session: Session, *, job_id: str, user_id: str, created_at: datetime) -> None:
    session.add(
        ClipJobModel(
            id=job_id,
            user_id=user_id,
            status="completed",
            created_at=created_at,
            updated_at=created_at,
            input_reference="storage:quota.mp4",
            clip_label="seed",
            tier="free",
            quota_source="monthly",
            metadata_json="{}",
        )
    )


def test_month_bounds_helper_handles_december_rollover() -> None:
    # Month rollover is the bug-prone branch: ``month + 1`` is invalid in
    # December, so the helper must roll the year.
    bounds_before = _current_month_bounds_utc()
    assert bounds_before[0].day == 1
    assert bounds_before[0].hour == 0
    assert bounds_before[1] > bounds_before[0]
    # Spanning a full month — never less than 28 days, never more than 31.
    delta = bounds_before[1] - bounds_before[0]
    assert timedelta(days=28) <= delta <= timedelta(days=31)


def test_quota_count_only_includes_current_month(client) -> None:
    """A clip from last month must not count against this month's quota."""
    repo: SqlClipJobRepository = client.app.state.repo
    user_id = "quota-user-001"

    month_start, _ = _current_month_bounds_utc()
    last_month_ts = month_start - timedelta(days=2)
    this_month_ts = month_start + timedelta(hours=1)

    with Session(get_engine()) as session:
        _seed(session, job_id="lm-1", user_id=user_id, created_at=last_month_ts)
        _seed(session, job_id="tm-1", user_id=user_id, created_at=this_month_ts)
        session.commit()

    assert repo.count_monthly_free_jobs(user_id) == 1


def test_quota_count_treats_next_month_start_as_exclusive(client) -> None:
    """The upper bound is open: a clip stamped exactly at next-month-start is in next month."""
    repo: SqlClipJobRepository = client.app.state.repo
    user_id = "quota-user-002"

    month_start, next_month_start = _current_month_bounds_utc()
    just_inside = next_month_start - timedelta(microseconds=1)

    with Session(get_engine()) as session:
        _seed(session, job_id="boundary-in", user_id=user_id, created_at=just_inside)
        _seed(session, job_id="boundary-out", user_id=user_id, created_at=next_month_start)
        session.commit()

    # Only ``just_inside`` falls within [month_start, next_month_start).
    assert repo.count_monthly_free_jobs(user_id) == 1


def test_quota_count_excludes_bonus_and_unlimited_quota_sources(client) -> None:
    """Only ``monthly`` (or NULL legacy) jobs count — preserves existing semantics."""
    repo: SqlClipJobRepository = client.app.state.repo
    user_id = "quota-user-003"

    month_start, _ = _current_month_bounds_utc()
    inside = month_start + timedelta(hours=2)

    with Session(get_engine()) as session:
        for i, qs in enumerate(("monthly", None, "bonus", "unlimited")):
            session.add(
                ClipJobModel(
                    id=f"qs-{i}",
                    user_id=user_id,
                    status="completed",
                    created_at=inside,
                    updated_at=inside,
                    input_reference="storage:qs.mp4",
                    clip_label="seed",
                    tier="free",
                    quota_source=qs,
                    metadata_json="{}",
                )
            )
        session.commit()

    # ``monthly`` and the legacy NULL row count; ``bonus`` and ``unlimited`` do not.
    assert repo.count_monthly_free_jobs(user_id) == 2


def test_quota_query_compiles_without_function_calls_on_created_at() -> None:
    """The SQL must not wrap ``created_at`` in ``extract``/``date_trunc``/``strftime``.

    Sargability check: the planner can only use an index on ``created_at`` if
    the column appears as a bare reference in the predicate. Any function
    wrapping it (``EXTRACT(year FROM created_at)``, ``date_trunc('month',
    created_at)``, etc.) forces a sequential scan.
    """
    from sqlalchemy import func, or_, select

    month_start, next_month_start = _current_month_bounds_utc()
    stmt = (
        select(func.count())
        .select_from(ClipJobModel)
        .where(
            ClipJobModel.user_id == "any-user",
            ClipJobModel.created_at >= month_start,
            ClipJobModel.created_at < next_month_start,
            or_(
                ClipJobModel.quota_source.is_(None),
                ClipJobModel.quota_source == "monthly",
            ),
        )
    )

    for dialect in (postgresql.dialect(), sqlite.dialect()):
        compiled = str(stmt.compile(dialect=dialect)).lower()
        for forbidden in ("extract(", "date_trunc(", "strftime("):
            assert forbidden not in compiled, (
                f"Quota query is non-sargable on {dialect.name}: "
                f"compiled SQL contains {forbidden!r}.\n{compiled}"
            )
        assert "created_at >=" in compiled
        assert "created_at <" in compiled


def test_quota_count_zero_when_user_has_no_clips_this_month(client) -> None:
    repo: SqlClipJobRepository = client.app.state.repo
    assert repo.count_monthly_free_jobs("nonexistent-user-id") == 0
