"""
Regression tests for the data-export endpoint's query count.

Previously, ``GET /api/v1/account/export`` issued one SELECT to list a user's
clips and then re-fetched each clip by primary key in a Python loop — a 1+N
pattern that scaled linearly with the user's clip count. The fix replaces that
with a single ``list_full_for_user`` query. These tests pin that contract by
counting the actual queries hit on the ``clip_jobs`` table during an export.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import get_engine
from app.domain.clip_job import ClipJobRecord


def _headers_for_email(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/session", json={"email": email})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _seed_clip(repo, *, user_id: str, idx: int) -> None:
    now = datetime.now(timezone.utc) - timedelta(minutes=idx)
    repo.create(
        ClipJobRecord(
            id=f"export-perf-{idx:03d}",
            user_id=user_id,
            status="completed",
            created_at=now,
            updated_at=now,
            input_reference=f"storage:perf/{idx}.mp4",
            failure_reason=None,
            result_json={"summary": "ok"},
            clip_label=f"clip-{idx}",
            tier="free",
            clip_metadata={"stance": "regular"},
            quota_source="monthly",
        )
    )


def test_export_clip_query_count_is_constant(client: TestClient) -> None:
    """Export must issue a single SELECT against ``clip_jobs`` regardless of clip count."""
    headers = _headers_for_email(client, "export-perf@onflow.test")
    me = client.get("/api/v1/account/me", headers=headers).json()
    user_id = me["user_id"]

    repo = client.app.state.repo
    seed_count = 25
    for i in range(seed_count):
        _seed_clip(repo, user_id=user_id, idx=i)

    clip_jobs_queries: list[str] = []

    def _on_query(_conn, _cursor, statement, _params, _context, _executemany) -> None:
        if "clip_jobs" in statement.lower():
            clip_jobs_queries.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", _on_query)
    try:
        r = client.get("/api/v1/account/export", headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", _on_query)

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["clips"]) == seed_count

    # The export path should hit ``clip_jobs`` exactly once now (a single
    # ``SELECT ... FROM clip_jobs WHERE user_id = ?``). Allow a tiny margin
    # purely for pessimistic ORM bookkeeping, but anything that scales with
    # ``seed_count`` is the regression we're guarding against.
    assert len(clip_jobs_queries) <= 2, (
        f"N+1 regression: {len(clip_jobs_queries)} queries hit clip_jobs for "
        f"{seed_count} clips. Statements: {clip_jobs_queries}"
    )


def test_export_clip_query_count_does_not_scale_with_clip_count(
    client: TestClient,
) -> None:
    """A user with 5 clips and a user with 30 clips must produce the same query count."""
    headers_small = _headers_for_email(client, "export-small@onflow.test")
    headers_large = _headers_for_email(client, "export-large@onflow.test")

    small_uid = client.get("/api/v1/account/me", headers=headers_small).json()["user_id"]
    large_uid = client.get("/api/v1/account/me", headers=headers_large).json()["user_id"]

    repo = client.app.state.repo
    for i in range(5):
        _seed_clip(repo, user_id=small_uid, idx=i)
    for i in range(30):
        _seed_clip(repo, user_id=large_uid, idx=100 + i)

    def _count_queries(headers: dict[str, str]) -> int:
        queries: list[str] = []

        def _on_query(_conn, _cursor, statement, _p, _c, _e) -> None:
            if "clip_jobs" in statement.lower():
                queries.append(statement)

        engine = get_engine()
        event.listen(engine, "before_cursor_execute", _on_query)
        try:
            r = client.get("/api/v1/account/export", headers=headers)
        finally:
            event.remove(engine, "before_cursor_execute", _on_query)
        assert r.status_code == 200
        return len(queries)

    small_q = _count_queries(headers_small)
    large_q = _count_queries(headers_large)
    assert small_q == large_q, (
        f"Query count scaled with clip volume: 5-clip user issued {small_q} queries, "
        f"30-clip user issued {large_q}. Expected identical (constant)."
    )


def test_existing_export_shape_preserved(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The single-query refactor must keep the export response shape identical."""
    repo = client.app.state.repo
    me = client.get("/api/v1/account/me", headers=auth_headers).json()
    user_id = me["user_id"]
    _seed_clip(repo, user_id=user_id, idx=0)

    r = client.get("/api/v1/account/export", headers=auth_headers)
    assert r.status_code == 200, r.text
    clip = r.json()["clips"][0]
    assert set(clip.keys()) == {
        "job_id",
        "status",
        "clip_label",
        "created_at",
        "failure_reason",
        "result",
        "clip_metadata",
    }
    assert clip["job_id"] == "export-perf-000"
    assert clip["clip_metadata"] == {"stance": "regular"}
