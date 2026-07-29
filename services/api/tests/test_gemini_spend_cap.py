"""Daily Gemini spend cap (ONFLOW_GEMINI_DAILY_SPEND_CAP_USD)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import create_db_tables, get_engine
from app.models import GeminiSpendDailyModel
from app.services.gemini_spend_cap import (
    check_daily_spend_cap,
    estimated_call_cost_cents,
    record_gemini_call,
)


@pytest.fixture(autouse=True)
def _ensure_spend_table(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    db = tmp_path / "spend_cap.db"
    monkeypatch.setenv("ONFLOW_DATABASE_URL", f"sqlite:///{db.as_posix()}")
    import app.core.database as database_module

    database_module._engine = None
    get_settings.cache_clear()
    create_db_tables()


def test_cap_disabled_when_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_GEMINI_DAILY_SPEND_CAP_USD", "0")
    get_settings.cache_clear()
    check_daily_spend_cap()  # no raise


def test_check_blocks_when_at_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONFLOW_GEMINI_DAILY_SPEND_CAP_USD", "1.00")
    get_settings.cache_clear()
    today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat()
    with Session(get_engine()) as session:
        session.add(
            GeminiSpendDailyModel(
                spend_date=today,
                spend_usd_cents=100,
                job_count=1,
            )
        )
        session.commit()
    with pytest.raises(HTTPException) as exc:
        check_daily_spend_cap()
    assert exc.value.status_code == 429
    assert "paused" in (exc.value.detail or "").lower()


def test_record_increments_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ONFLOW_GEMINI_DAILY_SPEND_CAP_USD", raising=False)
    get_settings.cache_clear()
    record_gemini_call("gemini-2.5-flash-lite")
    today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat()
    with Session(get_engine()) as session:
        row = session.get(GeminiSpendDailyModel, today)
        assert row is not None
        assert row.spend_usd_cents == estimated_call_cost_cents("gemini-2.5-flash-lite")
        assert row.job_count == 1


def test_estimated_cost_unknown_model_uses_upper_bound() -> None:
    assert estimated_call_cost_cents("unknown-model") == 20
