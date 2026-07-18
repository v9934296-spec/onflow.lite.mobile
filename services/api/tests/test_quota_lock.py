"""Per-user quota lock prevents monthly free over-serve within one process."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import get_settings
from app.domain.clip_job import ClipJobRecord
from app.repositories.clip_jobs import InMemoryClipJobRepository
from app.services import clip_quota


class _FakeIdentity:
    def __init__(self, tier: str = "free") -> None:
        self._tier = tier
        self.bonus = 0

    def get_user_tier(self, user_id: str) -> str:
        del user_id
        return self._tier

    def try_consume_one_bonus(self, user_id: str) -> bool:
        del user_id
        if self.bonus > 0:
            self.bonus -= 1
            return True
        return False

    def refund_one_bonus(self, user_id: str) -> bool:
        del user_id
        self.bonus += 1
        return True


class _Req:
    def __init__(self, db, repo) -> None:
        self.app = type("A", (), {})()
        self.app.state = type("S", (), {"db": db, "repo": repo})()


def test_concurrent_monthly_creates_respect_cap(monkeypatch) -> None:
    monkeypatch.setenv("ONFLOW_RATE_LIMIT_FREE", "3")
    get_settings.cache_clear()

    repo = InMemoryClipJobRepository()
    db = _FakeIdentity("free")
    req = _Req(db, repo)
    user_id = "u-lock"

    def _one(i: int) -> str:
        def build(tier: str, qs: str | None) -> ClipJobRecord:
            return ClipJobRecord.new_pending(
                f"job-{i}",
                user_id,
                f"storage:k{i}.mp4",
                tier=tier,
                quota_source=qs,
            )

        try:
            clip_quota.create_job_charging_quota(req, user_id, build)
            return "ok"
        except Exception as exc:
            return type(exc).__name__

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_one, i) for i in range(10)]
        results = [f.result() for f in as_completed(futs)]

    monthly = [
        j
        for j in repo.list_resumable() + []  # all jobs
        if True
    ]
    all_jobs = [repo.get(f"job-{i}") for i in range(10)]
    created = [j for j in all_jobs if j is not None]
    monthly_created = [j for j in created if j.quota_source == "monthly"]
    assert len(monthly_created) == 3
    assert results.count("ok") == 3
    assert results.count("HTTPException") == 7
