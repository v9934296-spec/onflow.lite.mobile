"""Queued hard-delete pipeline for user clip objects and clip job rows."""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from typing import Any

import structlog
from sqlmodel import Session, select

from app.repositories.clip_jobs import ClipJobRepository
from app.services.object_storage import ObjectStorage

logger = structlog.get_logger(__name__)

HARD_DELETE_TIMEOUT_SECONDS = 600


def _storage_key_from_input_reference(input_reference: str) -> str | None:
    ref = (input_reference or "").strip()
    if not ref:
        return None
    if ref.startswith("storage:"):
        key = ref.removeprefix("storage:").strip()
        return key or None
    return ref


def list_v1_clip_storage_keys(user_id: str) -> list[str]:
    """
    Collect object-storage keys owned by a user on V1 ``clips`` rows.

    Must be called **before** ``purge_user_owned_rows`` deletes those rows.
    Pending / abandoned uploads often have a ``storage_key`` with no
    corresponding ``clip_jobs`` row — hard-delete would otherwise miss them.
    """
    uid = (user_id or "").strip()
    if not uid:
        return []

    from app.core.database import get_engine
    from app.models import ClipModel

    keys: list[str] = []
    seen: set[str] = set()
    with Session(get_engine()) as session:
        for row in session.exec(select(ClipModel).where(ClipModel.user_id == uid)):
            for raw in (row.storage_key, row.thumbnail_key):
                key = (raw or "").strip()
                if key and key not in seen:
                    seen.add(key)
                    keys.append(key)
    return keys


def purge_retention_dir_for_user(user_id: str) -> int:
    """
    Remove consented retention copies under ``{retention_dir}/{user_id}/``.

    Returns the number of files removed (best-effort). Refuses path traversal.
    """
    uid = (user_id or "").strip()
    if not uid or ".." in uid or "/" in uid or "\\" in uid:
        return 0

    from app.core.config import get_settings

    root = get_settings().retention_dir_resolved.resolve()
    target = (root / uid).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        logger.warning(
            "hard_delete_retention_path_escape",
            user_id=uid,
            target=str(target),
        )
        return 0

    if not target.is_dir():
        return 0

    file_count = 0
    for path in target.rglob("*"):
        if path.is_file():
            file_count += 1

    try:
        shutil.rmtree(target)
        logger.info(
            "hard_delete_retention_purged",
            user_id=uid,
            file_count=file_count,
            path=str(target),
        )
    except OSError:
        logger.exception(
            "hard_delete_retention_purge_failed",
            user_id=uid,
            path=str(target),
        )
        return 0
    return file_count


async def enqueue_hard_delete(
    user_id: str,
    requested_at: datetime,
    *,
    extra_storage_keys: list[str] | None = None,
) -> None:
    """
    Enqueue hard-delete for a user.

    Redis-backed environments use ARQ. In local/dev environments without Redis,
    run synchronously in the request path: this is account deletion, so correctness
    is more important than latency and we intentionally avoid fire-and-forget.

    ``extra_storage_keys`` should include V1 clip object keys collected **before**
    clip rows are purged from the DB.
    """
    from app.services.job_queue import get_arq_pool

    keys = list(extra_storage_keys or [])

    pool = await get_arq_pool()
    if pool is not None:
        await pool.enqueue_job(
            "hard_delete_user_clips",
            user_id,
            keys,
            _job_id=f"hard_delete:{user_id}",
            _max_tries=3,
        )
        logger.info(
            "hard_delete_enqueued",
            user_id=user_id,
            requested_at=requested_at.isoformat(),
            extra_key_count=len(keys),
        )
        return

    logger.warning(
        "hard_delete_no_redis_running_sync",
        user_id=user_id,
        requested_at=requested_at.isoformat(),
        extra_key_count=len(keys),
    )
    await hard_delete_user_clips({}, user_id, keys)


async def hard_delete_user_clips(
    ctx: dict[str, Any],
    user_id: str,
    extra_storage_keys: list[str] | None = None,
) -> dict[str, Any]:
    """ARQ worker entrypoint. Purges object storage first, then clip job rows."""
    del ctx

    async def _run() -> dict[str, Any]:
        from app.core.database import get_engine
        from app.repositories.clip_jobs import SqlClipJobRepository
        from app.services.object_storage import build_storage

        engine = get_engine()
        repo = SqlClipJobRepository(lambda: Session(engine))
        storage = build_storage()
        return await _hard_delete_user_clips_impl(
            user_id,
            repo,
            storage,
            extra_storage_keys=extra_storage_keys,
        )

    return await asyncio.wait_for(_run(), timeout=HARD_DELETE_TIMEOUT_SECONDS)


async def _hard_delete_user_clips_impl(
    user_id: str,
    repo: ClipJobRepository,
    storage: ObjectStorage,
    *,
    extra_storage_keys: list[str] | None = None,
) -> dict[str, Any]:
    refs = repo.list_storage_refs_for_user(user_id)
    by_key: dict[str, list[str]] = {}
    job_ids_without_storage: list[str] = []

    for job_id, input_reference in refs:
        key = _storage_key_from_input_reference(input_reference)
        if key is None:
            job_ids_without_storage.append(job_id)
            logger.warning(
                "hard_delete_clip_missing_storage_key",
                user_id=user_id,
                job_id=job_id,
                input_reference=input_reference,
            )
            continue
        by_key.setdefault(key, []).append(job_id)

    # V1 clips (including abandoned pending uploads) whose keys were captured
    # before row purge. Merge so a key shared with a clip_job is deleted once.
    for raw in extra_storage_keys or []:
        key = (raw or "").strip()
        if key:
            by_key.setdefault(key, [])

    clip_count = len(refs)
    success_job_ids: list[str] = list(job_ids_without_storage)
    failed_keys: list[str] = []
    objects_deleted = 0

    logger.info(
        "hard_delete_started",
        user_id=user_id,
        clip_count=clip_count,
        object_count=len(by_key),
        extra_key_count=len(extra_storage_keys or []),
    )

    for key, job_ids in by_key.items():
        try:
            await storage.delete(key)
            objects_deleted += 1
        except Exception as exc:
            failed_keys.append(key)
            logger.warning(
                "hard_delete_storage_delete_failed",
                user_id=user_id,
                key=key,
                job_ids=job_ids,
                error=str(exc),
                exc_info=True,
            )
            continue
        success_job_ids.extend(job_ids)

    if success_job_ids:
        try:
            repo.delete_jobs_by_ids(success_job_ids)
        except Exception:
            logger.exception(
                "hard_delete_db_delete_failed",
                user_id=user_id,
                job_ids=success_job_ids,
            )
            raise

    retention_files = purge_retention_dir_for_user(user_id)

    success_count = len(success_job_ids)
    failure_count = len(failed_keys)
    report = {
        "user_id": user_id,
        "clip_count": clip_count,
        "object_count": len(by_key),
        "objects_deleted": objects_deleted,
        "success_count": success_count,
        "failure_count": failure_count,
        "failed_keys": failed_keys,
        "retention_files_purged": retention_files,
    }
    logger.info("hard_delete_complete", **report)
    return report
