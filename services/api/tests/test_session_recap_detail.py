"""GET /api/v1/sessions/{id}/recap — progression recap aggregation (Step 5E).

Clip ordering is newest-first (created_at descending).
Metrics use existing data only; unavailable metrics are null, never guessed.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import get_engine
from app.models import ClipModel, SkateSessionModel


def _create_session(client: TestClient) -> str:
    r = client.post(
        "/api/v1/sessions",
        json={"spot_label": "Fremont Skatepark", "focus_trick": "kickflip"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _insert_session(
    user_id: str, started: datetime, ended: datetime | None
) -> str:
    sid = str(uuid.uuid4())
    with Session(get_engine()) as db:
        db.add(
            SkateSessionModel(
                id=sid,
                user_id=user_id,
                spot_label="Direct Spot",
                started_at=started,
                ended_at=ended,
            )
        )
        db.commit()
    return sid


def _insert_clip(
    session_id: str,
    user_id: str,
    *,
    landed: bool | None = None,
    pte: int | None = None,
    created_at: datetime | None = None,
    trick_id: str | None = None,
    thumbnail_url: str | None = None,
    storage_url: str = "",
) -> str:
    cid = str(uuid.uuid4())
    with Session(get_engine()) as db:
        db.add(
            ClipModel(
                id=cid,
                user_id=user_id,
                session_id=session_id,
                storage_key=f"clips/{cid}.mp4",
                storage_url=storage_url,
                thumbnail_url=thumbnail_url,
                trick_id=trick_id,
                landed=landed,
                pte_rating=pte,
                upload_status="ready",
                created_at=created_at or datetime.now(timezone.utc),
            )
        )
        db.commit()
    return cid


def test_owner_can_fetch_recap(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    r = authed_client.get(f"/api/v1/sessions/{sid}/recap")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"] == sid
    assert body["spot"] == "Fremont Skatepark"
    assert body["focus_trick"] == "kickflip"
    assert body["clips_count"] == 0
    assert body["clips"] == []


def test_other_user_cannot_fetch_recap(client: TestClient) -> None:
    client.headers["Authorization"] = "Bearer dev:owner-aaa"
    sid = _create_session(client)
    client.headers["Authorization"] = "Bearer dev:intruder-bbb"
    r = client.get(f"/api/v1/sessions/{sid}/recap")
    assert r.status_code == 404, r.text


def test_missing_session_returns_404(authed_client: TestClient) -> None:
    r = authed_client.get(f"/api/v1/sessions/{uuid.uuid4()}/recap")
    assert r.status_code == 404, r.text


def test_empty_session_is_stable(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["clips_count"] == 0
    assert body["attempts_count"] == 0
    assert body["landed_count"] is None
    assert body["landed_rate"] is None
    assert body["best_pte_score"] is None
    assert body["average_pte_score"] is None
    assert body["clips"] == []


def test_duration_calculated_when_both_timestamps_present(
    authed_client: TestClient,
) -> None:
    started = datetime(2026, 6, 1, 18, 0, 0, tzinfo=timezone.utc)
    ended = started + timedelta(minutes=30)
    sid = _insert_session("test-user-001", started, ended)
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["duration_seconds"] == 1800


def test_duration_null_when_not_ended(authed_client: TestClient) -> None:
    started = datetime(2026, 6, 1, 18, 0, 0, tzinfo=timezone.utc)
    sid = _insert_session("test-user-001", started, None)
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["duration_seconds"] is None
    assert body["ended_at"] is None


def test_pte_aggregates_when_present(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    for score in (5, 8, 6):
        _insert_clip(sid, "test-user-001", pte=score)
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["best_pte_score"] == 8
    assert body["average_pte_score"] == 6.3
    assert body["clips_count"] == 3
    assert body["attempts_count"] == 0


def test_missing_pte_returns_null(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    _insert_clip(sid, "test-user-001", pte=None)
    _insert_clip(sid, "test-user-001", pte=None)
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["best_pte_score"] is None
    assert body["average_pte_score"] is None
    assert body["clips_count"] == 2


def test_landed_aggregates_when_present(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    _insert_clip(sid, "test-user-001", landed=True)
    _insert_clip(sid, "test-user-001", landed=True)
    _insert_clip(sid, "test-user-001", landed=False)
    _insert_clip(sid, "test-user-001", landed=True)
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["landed_count"] == 3
    assert body["landed_rate"] == 0.75  # 3 landed / 4 clips


def test_missing_landed_returns_null(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    _insert_clip(sid, "test-user-001", landed=None)
    _insert_clip(sid, "test-user-001", landed=None)
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["landed_count"] is None
    assert body["landed_rate"] is None


def test_clips_ordered_newest_first(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    base = datetime(2026, 6, 1, 18, 0, 0, tzinfo=timezone.utc)
    oldest = _insert_clip(sid, "test-user-001", created_at=base)
    middle = _insert_clip(sid, "test-user-001", created_at=base + timedelta(minutes=5))
    newest = _insert_clip(sid, "test-user-001", created_at=base + timedelta(minutes=10))
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    ids = [c["clip_id"] for c in body["clips"]]
    assert ids == [newest, middle, oldest]


def test_clip_fields_round_trip(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    _insert_clip(
        sid,
        "test-user-001",
        landed=True,
        pte=7,
        trick_id="kickflip",
        thumbnail_url="https://cdn.test/thumb.jpg",
        storage_url="https://cdn.test/clip.mp4",
    )
    clip = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()["clips"][0]
    assert clip["thumbnail_url"] == "https://cdn.test/thumb.jpg"
    assert clip["video_playback_url"] == "https://cdn.test/clip.mp4"
    assert clip["landed"] is True
    assert clip["pte_score"] == 7
    assert clip["trick"] is not None
    assert clip["stance"] is None  # no per-clip stance in V1


def test_attempts_count_from_synced_attempts_not_clips(authed_client: TestClient) -> None:
    sid = _create_session(authed_client)
    for _ in range(2):
        _insert_clip(sid, "test-user-001", pte=6)
    sync = authed_client.post(
        "/api/v1/session-attempts/sync",
        json={
            "attempts": [
                {
                    "id": "recap-a1",
                    "session_id": sid,
                    "trick_id": "kickflip",
                    "canonical_name": "Kickflip",
                    "outcome": "landed",
                    "logged_at": "2026-07-17T12:00:00Z",
                },
                {
                    "id": "recap-a2",
                    "session_id": sid,
                    "trick_id": "kickflip",
                    "canonical_name": "Kickflip",
                    "outcome": "missed",
                    "logged_at": "2026-07-17T12:01:00Z",
                },
                {
                    "id": "recap-a3",
                    "session_id": sid,
                    "trick_id": "heelflip",
                    "canonical_name": "Heelflip",
                    "outcome": "landed",
                    "logged_at": "2026-07-17T12:02:00Z",
                },
            ]
        },
    )
    assert sync.status_code == 200, sync.text
    body = authed_client.get(f"/api/v1/sessions/{sid}/recap").json()
    assert body["clips_count"] == 2
    assert body["attempts_count"] == 3
    assert body["landed_count"] == 2
    assert body["landed_rate"] == 0.67
