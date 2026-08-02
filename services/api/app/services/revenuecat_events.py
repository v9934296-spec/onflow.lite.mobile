"""Atomic RevenueCat event application.

The deduplication row and the entitlement/credit mutation must commit together.
If the mutation fails, the event id remains replayable; if the event is a duplicate,
no user state is touched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.database import get_engine
from app.models import RcWebhookDedupModel, UserModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RevenueCatMutationResult:
    duplicate: bool
    user_id: str | None
    bonus_total: int | None = None


def _normalized_candidates(candidate_user_ids: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in candidate_user_ids:
        value = (raw or "").strip()
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _locked_user(
    session: Session,
    candidate_user_ids: Iterable[str],
    rc_customer_id: str | None,
) -> UserModel | None:
    for user_id in _normalized_candidates(candidate_user_ids):
        row = session.exec(
            select(UserModel).where(UserModel.id == user_id).with_for_update()
        ).first()
        if row is not None:
            return row

    rc_id = (rc_customer_id or "").strip()
    if rc_id:
        return session.exec(
            select(UserModel)
            .where(UserModel.rc_customer_id == rc_id)
            .with_for_update()
        ).first()
    return None


def _mutate_user(
    row: UserModel,
    *,
    new_tier: str | None,
    bonus_delta: int,
    rc_customer_id: str | None,
) -> int | None:
    if new_tier is not None:
        row.tier = new_tier

    bonus_total: int | None = None
    if bonus_delta:
        row.bonus_analyses = int(row.bonus_analyses or 0) + bonus_delta
        bonus_total = row.bonus_analyses

    rc_id = (rc_customer_id or "").strip()
    if rc_id:
        row.rc_customer_id = rc_id

    return bonus_total


def apply_revenuecat_mutation(
    *,
    event_id: str,
    candidate_user_ids: Iterable[str],
    rc_customer_id: str | None,
    new_tier: str | None = None,
    bonus_delta: int = 0,
) -> RevenueCatMutationResult:
    """Apply one entitlement or bonus mutation exactly once.

    The event-id insert is flushed first to claim the event. The user row is then
    locked and mutated in the same transaction. Any exception rolls back both the
    mutation and the dedup claim, so RevenueCat can safely retry the same event.
    """
    eid = (event_id or "").strip()
    if not eid:
        raise ValueError("RevenueCat event id is required")
    if new_tier is None and bonus_delta == 0:
        raise ValueError("RevenueCat mutation requires a tier change or bonus delta")
    if bonus_delta < 0:
        raise ValueError("RevenueCat bonus delta cannot be negative")

    with Session(get_engine()) as session:
        try:
            session.add(RcWebhookDedupModel(event_id=eid, created_at=_utcnow()))
            session.flush()
        except IntegrityError:
            session.rollback()
            return RevenueCatMutationResult(duplicate=True, user_id=None)

        try:
            row = _locked_user(session, candidate_user_ids, rc_customer_id)
            if row is None:
                # Unknown users are not consumed. A later retry can succeed after
                # RevenueCat identity linking or account creation is repaired.
                session.rollback()
                return RevenueCatMutationResult(duplicate=False, user_id=None)

            bonus_total = _mutate_user(
                row,
                new_tier=new_tier,
                bonus_delta=bonus_delta,
                rc_customer_id=rc_customer_id,
            )
            session.add(row)
            session.commit()
            return RevenueCatMutationResult(
                duplicate=False,
                user_id=row.id,
                bonus_total=bonus_total,
            )
        except Exception:
            session.rollback()
            raise


def record_revenuecat_noop(event_id: str) -> bool:
    """Record a no-op lifecycle event once; return False for a duplicate."""
    eid = (event_id or "").strip()
    if not eid:
        raise ValueError("RevenueCat event id is required")

    with Session(get_engine()) as session:
        try:
            session.add(RcWebhookDedupModel(event_id=eid, created_at=_utcnow()))
            session.commit()
            return True
        except IntegrityError:
            session.rollback()
            return False
