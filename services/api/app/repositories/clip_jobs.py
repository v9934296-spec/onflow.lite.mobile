from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.domain.clip_job import ClipJobRecord
from app.models import ClipJobModel


def _current_month_bounds_utc() -> tuple[datetime, datetime]:
    """Return ``(month_start, next_month_start)`` for *now* in UTC.

    The bounds are computed in Python so SQL predicates can stay as plain
    range comparisons against ``created_at``. That keeps queries sargable —
    Postgres can use an index on ``(user_id, created_at)`` directly. Wrapping
    the column in ``EXTRACT(...)`` or ``date_trunc(...)`` would defeat that
    and force a sequential scan.
    """
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)
    return month_start, next_month_start


@runtime_checkable
class ClipJobRepository(Protocol):
    def create(self, job: ClipJobRecord) -> None: ...
    def get(self, job_id: str) -> ClipJobRecord | None: ...
    def update(self, job: ClipJobRecord) -> None: ...
    def get_for_user(self, job_id: str, user_id: str) -> ClipJobRecord | None: ...
    def list_for_user(self, user_id: str, *, limit: int) -> list[dict[str, Any]]: ...
    def list_full_for_user(self, user_id: str, *, limit: int) -> list[ClipJobRecord]: ...
    def iter_all_for_user(
        self, user_id: str, *, batch_size: int = 1000
    ) -> Iterator[ClipJobRecord]: ...
    def list_storage_refs_for_user(self, user_id: str) -> list[tuple[str, str]]: ...
    def list_resumable(self) -> list[ClipJobRecord]: ...
    def count_monthly_free_jobs(self, user_id: str) -> int: ...
    def count_active_clip_jobs(self, user_id: str) -> int: ...
    def delete_all_for_user(self, user_id: str) -> None: ...
    def delete_jobs_by_ids(self, job_ids: list[str]) -> None: ...


class InMemoryClipJobRepository:
    """Process-local storage. Used for tests without a database file."""

    def __init__(self) -> None:
        self._by_id: dict[str, ClipJobRecord] = {}

    def create(self, job: ClipJobRecord) -> None:
        self._by_id[job.id] = job

    def get(self, job_id: str) -> ClipJobRecord | None:
        return self._by_id.get(job_id)

    def update(self, job: ClipJobRecord) -> None:
        self._by_id[job.id] = job

    def get_for_user(self, job_id: str, user_id: str) -> ClipJobRecord | None:
        j = self._by_id.get(job_id)
        return j if j and j.user_id == user_id else None

    def list_for_user(self, user_id: str, *, limit: int) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 100))
        rows = [j for j in self._by_id.values() if j.user_id == user_id]
        rows.sort(key=lambda x: x.updated_at, reverse=True)
        out: list[dict[str, Any]] = []
        for j in rows[:lim]:
            ts = j.updated_at.isoformat().replace("+00:00", "Z")
            out.append(
                {
                    "id": j.id,
                    "status": j.status,
                    "clip_label": j.clip_label,
                    "updated_at": ts,
                    "failure_reason": j.failure_reason,
                }
            )
        return out

    def list_resumable(self) -> list[ClipJobRecord]:
        return [
            j
            for j in self._by_id.values()
            if j.status in ("pending", "processing")
        ]

    def list_full_for_user(self, user_id: str, *, limit: int) -> list[ClipJobRecord]:
        # Mirrors list_for_user's safety cap so the export endpoint cannot
        # be coerced into pulling unbounded rows in a single request.
        lim = max(1, min(limit, 100))
        rows = [j for j in self._by_id.values() if j.user_id == user_id]
        rows.sort(key=lambda x: x.updated_at, reverse=True)
        return rows[:lim]

    def iter_all_for_user(
        self, user_id: str, *, batch_size: int = 1000
    ) -> Iterator[ClipJobRecord]:
        # Full, UNCAPPED export of a user's own rows (GDPR/CCPA completeness).
        del batch_size  # in-memory has no query cost to batch
        rows = [j for j in self._by_id.values() if j.user_id == user_id]
        rows.sort(key=lambda x: x.updated_at, reverse=True)
        yield from rows

    def list_storage_refs_for_user(self, user_id: str) -> list[tuple[str, str]]:
        return [
            (j.id, j.input_reference)
            for j in self._by_id.values()
            if j.user_id == user_id
        ]

    def count_monthly_free_jobs(self, user_id: str) -> int:
        # Mirrors the SQL implementation: compare ``created_at`` against
        # pre-computed month bounds. The in-memory path is still O(N) over the
        # process-local map, but the bounds match exactly what Postgres sees.
        month_start, next_month_start = _current_month_bounds_utc()
        n = 0
        for j in self._by_id.values():
            if j.user_id != user_id:
                continue
            d = j.created_at
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d < month_start or d >= next_month_start:
                continue
            qs = j.quota_source
            if qs is None or qs == "monthly":
                n += 1
        return n

    def count_active_clip_jobs(self, user_id: str) -> int:
        return sum(
            1
            for j in self._by_id.values()
            if j.user_id == user_id and j.status in ("pending", "processing")
        )

    def delete_all_for_user(self, user_id: str) -> None:
        for jid in [k for k, v in self._by_id.items() if v.user_id == user_id]:
            del self._by_id[jid]

    def delete_jobs_by_ids(self, job_ids: list[str]) -> None:
        for jid in job_ids:
            self._by_id.pop(jid, None)

    def clear(self) -> None:
        self._by_id.clear()


class SqlClipJobRepository:
    """PostgreSQL/SQLite-backed persistent repository."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def _to_record(self, m: ClipJobModel) -> ClipJobRecord:
        return ClipJobRecord(
            id=m.id,
            user_id=m.user_id,
            status=m.status,  # type: ignore[arg-type]
            created_at=m.created_at,
            updated_at=m.updated_at,
            input_reference=m.input_reference,
            failure_reason=m.failure_reason,
            result_json=m.result_json,
            clip_label=m.clip_label or "untagged",
            tier=m.tier if m.tier in ("free", "pro") else "free",
            clip_metadata=m.clip_metadata,
            quota_source=m.quota_source,
        )

    def _from_record(self, r: ClipJobRecord) -> ClipJobModel:
        m = ClipJobModel(
            id=r.id,
            user_id=r.user_id,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
            input_reference=r.input_reference,
            failure_reason=r.failure_reason,
            clip_label=r.clip_label,
            tier=r.tier,
            quota_source=r.quota_source,
        )
        m.result_json = r.result_json
        m.clip_metadata = r.clip_metadata
        return m

    def create(self, job: ClipJobRecord) -> None:
        with self._session_factory() as session:
            session.add(self._from_record(job))
            session.commit()

    def get(self, job_id: str) -> ClipJobRecord | None:
        with self._session_factory() as session:
            m = session.get(ClipJobModel, job_id)
            return self._to_record(m) if m else None

    def update(self, job: ClipJobRecord) -> None:
        with self._session_factory() as session:
            m = session.get(ClipJobModel, job.id)
            if m is None:
                return
            m.status = job.status
            m.updated_at = job.updated_at
            m.failure_reason = job.failure_reason
            m.result_json = job.result_json
            m.clip_label = job.clip_label
            m.tier = job.tier
            m.input_reference = job.input_reference
            m.quota_source = job.quota_source
            session.add(m)
            session.commit()

    def get_for_user(self, job_id: str, user_id: str) -> ClipJobRecord | None:
        with self._session_factory() as session:
            m = session.get(ClipJobModel, job_id)
            if m is None or m.user_id != user_id:
                return None
            return self._to_record(m)

    def list_for_user(self, user_id: str, *, limit: int) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 100))
        with self._session_factory() as session:
            stmt = (
                select(ClipJobModel)
                .where(ClipJobModel.user_id == user_id)
                .order_by(ClipJobModel.updated_at.desc())
                .limit(lim)
            )
            rows = list(session.exec(stmt))
            out: list[dict[str, Any]] = []
            for m in rows:
                ts = m.updated_at.isoformat().replace("+00:00", "Z")
                out.append(
                    {
                        "id": m.id,
                        "status": m.status,
                        "clip_label": m.clip_label,
                        "updated_at": ts,
                        "failure_reason": m.failure_reason,
                    }
                )
            return out

    def list_resumable(self) -> list[ClipJobRecord]:
        with self._session_factory() as session:
            stmt = (
                select(ClipJobModel)
                .where(ClipJobModel.status.in_(("pending", "processing")))
                .order_by(ClipJobModel.created_at.asc())
            )
            rows = list(session.exec(stmt))
            return [self._to_record(m) for m in rows]

    def list_full_for_user(self, user_id: str, *, limit: int) -> list[ClipJobRecord]:
        # Single SELECT — replaces the export endpoint's previous
        # list_for_user + per-row repo.get loop (1 + N queries).
        # Cap mirrors list_for_user so the export cannot pull unbounded rows.
        lim = max(1, min(limit, 100))
        with self._session_factory() as session:
            stmt = (
                select(ClipJobModel)
                .where(ClipJobModel.user_id == user_id)
                .order_by(ClipJobModel.updated_at.desc())
                .limit(lim)
            )
            rows = list(session.exec(stmt))
            return [self._to_record(m) for m in rows]

    def iter_all_for_user(
        self, user_id: str, *, batch_size: int = 1000
    ) -> Iterator[ClipJobRecord]:
        # Full, UNCAPPED export of a user's own rows (GDPR/CCPA completeness).
        # Reads in bounded batches so a large history can't materialize the whole
        # table at once. For a user whose history fits in one batch this issues a
        # single SELECT (preserving the export endpoint's constant-query contract).
        batch = max(1, batch_size)
        offset = 0
        while True:
            with self._session_factory() as session:
                stmt = (
                    select(ClipJobModel)
                    .where(ClipJobModel.user_id == user_id)
                    .order_by(ClipJobModel.updated_at.desc(), ClipJobModel.id.desc())
                    .offset(offset)
                    .limit(batch)
                )
                records = [self._to_record(m) for m in session.exec(stmt)]
            yield from records
            if len(records) < batch:
                break
            offset += batch

    def list_storage_refs_for_user(self, user_id: str) -> list[tuple[str, str]]:
        with self._session_factory() as session:
            stmt = (
                select(ClipJobModel.id, ClipJobModel.input_reference)
                .where(ClipJobModel.user_id == user_id)
                .order_by(ClipJobModel.created_at.asc())
            )
            return [(str(row[0]), str(row[1] or "")) for row in session.exec(stmt)]

    def count_monthly_free_jobs(self, user_id: str) -> int:
        # Range bounds keep this sargable: predicates compare ``created_at``
        # to bare timestamps so the planner can pick an index on
        # ``(user_id, created_at)``. Wrapping ``created_at`` in
        # ``EXTRACT(...)`` would force a sequential scan.
        month_start, next_month_start = _current_month_bounds_utc()
        with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(ClipJobModel)
                .where(
                    ClipJobModel.user_id == user_id,
                    ClipJobModel.created_at >= month_start,
                    ClipJobModel.created_at < next_month_start,
                    or_(
                        ClipJobModel.quota_source.is_(None),
                        ClipJobModel.quota_source == "monthly",
                    ),
                )
            )
            return int(session.exec(stmt).one())

    def count_active_clip_jobs(self, user_id: str) -> int:
        with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(ClipJobModel)
                .where(
                    ClipJobModel.user_id == user_id,
                    ClipJobModel.status.in_(("pending", "processing")),
                )
            )
            return int(session.exec(stmt).one())

    def delete_all_for_user(self, user_id: str) -> None:
        with self._session_factory() as session:
            for m in session.exec(select(ClipJobModel).where(ClipJobModel.user_id == user_id)):
                session.delete(m)
            session.commit()

    def delete_jobs_by_ids(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        with self._session_factory() as session:
            for m in session.exec(select(ClipJobModel).where(ClipJobModel.id.in_(job_ids))):
                session.delete(m)
            session.commit()
