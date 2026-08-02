"""Atomic RevenueCat event application.

The deduplication row and the entitlement/credit mutation must commit together.
If the mutation fails, the event id remains replayable; if the event is a duplicate,
no user state is touched. Entitlement mutations also use RevenueCat's event timestamp
so out-of-order delivery cannot let an older expiration overwrite a newer renewal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.database import get_engine
from app.models import RcWebhookDedupModel, UserModel
from app.models_revenuecat import RcEntitlementStateModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RevenueCatMutationResult:
    duplicate: bool
    user_id: str | None
    bonus_total: int | None = None
    stale: bool = False


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
    candidates = _normalized_candidates(candidate_user_ids)
    for user_id in candidates:
        row = session.exec(
            select(UserModel).where(UserModel.id == user_id).with_for_update()
        ).first()
        if row is not None:
            return row

    rc_candidates = _normalized_candidates([rc_customer_id or "", *candidates])
    if rc_candidates:
        return session.exec(
            select(UserModel)
            .where(UserModel.rc_customer_id.in_(rc_candidates))
            .with_for_update()
        ).first()
    return None


def _locked_entitlement_state(
    session: Session,
    user_id: str,
) -> RcEntitlementStateModel:
    state = session.exec(
        select(RcEntitlementStateModel)
        .where(RcEntitlementStateModel.user_id == user_id)
        .with_for_update()
    ).first()
    if state is not None:
        return state

    state = RcEntitlementStateModel(user_id=user_id, updated_at=_utcnow())
    session.add(state)
    session.flush()
    return state


def _is_stale_entitlement_event(
    state: RcEntitlementStateModel,
    *,
    event_timestamp_ms: int | None,
    new_tier: str,
) -> bool:
    """Return True when this mutation is older than the stored entitlement state.

    RevenueCat documents ``event_timestamp_ms`` as the ordering timestamp. On an
    exact timestamp tie, prefer preserving paid access: a Pro grant may replace a
    free state, but a free mutation may not overwrite an already-applied Pro grant.
    """
    if event_timestamp_ms is None or state.last_event_timestamp_ms is None:
        return False
    if event_timestamp_ms < state.last_event_timestamp_ms:
        return True
    if event_timestamp_ms > state.last_event_timestamp_ms:
        return False

    incoming_rank = 1 if new_tier == "pro" else 0
    stored_rank = 1 if state.last_tier == "pro" else 0
    return incoming_rank <= stored_rank


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
    event_timestamp_ms: int | None = None,
) -> RevenueCatMutationResult:
    """Apply one entitlement or bonus mutation exactly once.

    The event-id insert is flushed first to claim the event. The user row is then
    locked and mutated in the same transaction. Any exception rolls back both the
    mutation and the dedup claim, so RevenueCat can safely retry the same event.
    Entitlement mutations are ordered by ``event_timestamp_ms`` under the same lock.
    """
    eid = (event_id or "").strip()
    if not eid:
        raise ValueError("RevenueCat event id is required")
    if new_tier is None and bonus_delta == 0:
        raise ValueError("RevenueCat mutation requires a tier change or bonus delta")
    if bonus_delta < 0:
        raise ValueError("RevenueCat bonus delta cannot be negative")
    if event_timestamp_ms is not None and event_timestamp_ms < 0:
        raise ValueError("RevenueCat event timestamp cannot be negative")

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
                # Roll back the event claim. The webhook endpoint returns 503 for
                # paid mutations so RevenueCat retries after identity linking.
                session.rollback()
                return RevenueCatMutationResult(duplicate=False, user_id=None)

            state: RcEntitlementStateModel | None = None
            if new_tier is not None:
                state = _locked_entitlement_state(session, row.id)
                if _is_stale_entitlement_event(
                    state,
                    event_timestamp_ms=event_timestamp_ms,
                    new_tier=new_tier,
                ):
                    # Commit only the event-id claim. This stale delivery must never
                    # be able to mutate the account on a later manual replay.
                    session.commit()
                    return RevenueCatMutationResult(
                        duplicate=False,
                        user_id=row.id,
                        stale=True,
                    )

            bonus_total = _mutate_user(
                row,
                new_tier=new_tier,
                bonus_delta=bonus_delta,
                rc_customer_id=rc_customer_id,
            )
            session.add(row)

            if state is not None:
                if event_timestamp_ms is not None:
                    state.last_event_timestamp_ms = event_timestamp_ms
                state.last_event_id = eid
                state.last_tier = new_tier
                state.updated_at = _utcnow()
                session.add(state)

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
