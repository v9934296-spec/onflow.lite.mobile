from __future__ import annotations

from collections.abc import Callable
from typing import BinaryIO

from app.domain.clip_job import ClipJobRecord
from app.repositories.clip_jobs import InMemoryClipJobRepository
from app.services.deletion_queue import _hard_delete_user_clips_impl


class SpyStorage:
    def __init__(
        self,
        *,
        existing_keys: set[str] | None = None,
        fail_keys: set[str] | None = None,
        on_delete: Callable[[str], None] | None = None,
    ) -> None:
        self.existing_keys = set(existing_keys or set())
        self.fail_keys = set(fail_keys or set())
        self.deleted_keys: list[str] = []
        self._on_delete = on_delete

    async def put(self, key: str, data: BinaryIO, content_type: str = "video/mp4") -> str:
        del data, content_type
        self.existing_keys.add(key)
        return f"storage:{key}"

    async def get_path(self, key: str) -> str:
        return key

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        if self._on_delete is not None:
            self._on_delete(key)
        if key in self.fail_keys:
            raise RuntimeError(f"delete failed for {key}")
        self.existing_keys.discard(key)

    async def exists(self, key: str) -> bool:
        return key in self.existing_keys


class DeleteFailsOnceRepository(InMemoryClipJobRepository):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_delete = True

    def delete_jobs_by_ids(self, job_ids: list[str]) -> None:
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise RuntimeError("db delete failed")
        super().delete_jobs_by_ids(job_ids)


def _repo_with_clips(user_id: str, keys: list[str]) -> InMemoryClipJobRepository:
    repo = InMemoryClipJobRepository()
    for idx, key in enumerate(keys):
        job_id = f"job-{idx}"
        repo.create(
            ClipJobRecord.new_pending(
                job_id,
                user_id,
                f"storage:{key}",
                clip_label=f"clip-{idx}",
            )
        )
    return repo


async def test_hard_delete_deletes_each_storage_key_then_clip_rows() -> None:
    user_id = "user-001"
    keys = ["clips/a.mp4", "clips/b.mp4", "clips/c.mp4"]
    repo = _repo_with_clips(user_id, keys)

    def assert_rows_still_exist(_key: str) -> None:
        assert repo.list_for_user(user_id, limit=10)

    storage = SpyStorage(existing_keys=set(keys), on_delete=assert_rows_still_exist)

    report = await _hard_delete_user_clips_impl(user_id, repo, storage)

    assert storage.deleted_keys == keys
    assert repo.list_for_user(user_id, limit=10) == []
    assert report["clip_count"] == 3
    assert report["success_count"] == 3
    assert report["failure_count"] == 0


async def test_hard_delete_continues_after_storage_failure_and_keeps_failed_row() -> None:
    user_id = "user-002"
    keys = ["clips/a.mp4", "clips/b.mp4", "clips/c.mp4"]
    repo = _repo_with_clips(user_id, keys)
    storage = SpyStorage(existing_keys=set(keys), fail_keys={"clips/b.mp4"})

    report = await _hard_delete_user_clips_impl(user_id, repo, storage)

    assert storage.deleted_keys == keys
    remaining = repo.list_for_user(user_id, limit=10)
    assert [row["id"] for row in remaining] == ["job-1"]
    assert "clips/b.mp4" in storage.existing_keys
    assert report["success_count"] == 2
    assert report["failure_count"] == 1
    assert report["failed_keys"] == ["clips/b.mp4"]


async def test_hard_delete_is_noop_when_rerun_after_success() -> None:
    user_id = "user-003"
    keys = ["clips/a.mp4"]
    repo = _repo_with_clips(user_id, keys)
    storage = SpyStorage(existing_keys=set(keys))

    first = await _hard_delete_user_clips_impl(user_id, repo, storage)
    second = await _hard_delete_user_clips_impl(user_id, repo, storage)

    assert first["success_count"] == 1
    assert second["clip_count"] == 0
    assert second["success_count"] == 0
    assert repo.list_for_user(user_id, limit=10) == []


async def test_hard_delete_retries_storage_success_when_db_delete_failed() -> None:
    user_id = "user-004"
    key = "clips/retry.mp4"
    repo = DeleteFailsOnceRepository()
    repo.create(
        ClipJobRecord.new_pending(
            "job-retry",
            user_id,
            f"storage:{key}",
            clip_label="retry",
        )
    )
    storage = SpyStorage(existing_keys={key})

    try:
        await _hard_delete_user_clips_impl(user_id, repo, storage)
    except RuntimeError as exc:
        assert str(exc) == "db delete failed"
    else:
        raise AssertionError("expected db delete failure")

    assert storage.deleted_keys == [key]
    assert storage.existing_keys == set()
    assert repo.get("job-retry") is not None

    report = await _hard_delete_user_clips_impl(user_id, repo, storage)

    assert storage.deleted_keys == [key, key]
    assert storage.existing_keys == set()
    assert repo.list_for_user(user_id, limit=10) == []
    assert report["success_count"] == 1
