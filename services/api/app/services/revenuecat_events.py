"""Atomic RevenueCat event application.

The deduplication row and the entitlement/credit mutation commit together.
Entitlement state is ordered independently per Store product so delayed delivery
cannot let an older expiration overwrite a newer renewal, and expiring one product
cannot revoke Pro while another configured Pro product remains active.
"""

from __future__ import annotations

import json
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
    tier: str | None = None
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

    state = RcEntitlementStateModel(
        user_id=user_id,
        product_states_json="{}",
        updated_at=_utcnow(),
    )
    session.add(state)
    session.flush()
    return state


def _load_product_states(state: RcEntitlementStateModel) -> dict[str, dict]:
    try:
        parsed = json.loads(state.product_states_json or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Stored RevenueCat product state is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Stored RevenueCat product state must be an object")

    normalized: dict[str, dict] = {}
    for raw_product_id, raw_entry in parsed.items():
        product_id = str(raw_product_id or "").strip()
        if not product_id or not isinstance(raw_entry, dict):
            raise RuntimeError("Stored RevenueCat product state is malformed")
        active = raw_entry.get("active")
        if not isinstance(active, bool):
            raise RuntimeError("Stored RevenueCat product active flag is malformed")
        timestamp = raw_entry.get("event_timestamp_ms")
        if timestamp is not None and (isinstance(timestamp, bool) or not isinstance(timestamp, int)):
            raise RuntimeError("Stored RevenueCat product timestamp is malformed")
        event_id = raw_entry.get("event_id")
        normalized[product_id] = {
            "active": active,
            "event_timestamp_ms": timestamp,
            "event_id": str(event_id or ""),
        }
    return normalized


def _is_stale_product_event(
    existing: dict | None,
    *,
    event_timestamp_ms: int | None,
    active: bool,
) -> bool:
    """Order one product's events and preserve access on exact timestamp ties."""
    if existing is None:
        return False

    stored_timestamp = existing.get("event_timestamp_ms")
    stored_active = bool(existing.get("active"))

    # Once a product has an ordered state, a malformed/unordered delivery must not
    # overwrite it. RevenueCat production events include event_timestamp_ms.
    if event_timestamp_ms is None:
        return stored_timestamp is not None
    if stored_timestamp is None:
        return False
    if event_timestamp_ms < stored_timestamp:
        return True
    if event_timestamp_ms > stored_timestamp:
        return False

    # Same timestamp: identical state is redundant. If states conflict, retain
    # paid access rather than letting a tied expiration revoke it.
    if active == stored_active:
        return True
    return stored_active and not active


def _apply_product_entitlement_event(
    state: RcEntitlementStateModel,
    *,
    product_id: str,
    active: bool,
    event_timestamp_ms: int | None,
    event_id: str,
    pro_product_ids: set[str],
) -> tuple[bool, str]:
    states = _load_product_states(state)
    existing = states.get(product_id)
    if _is_stale_product_event(
        existing,
        event_timestamp_ms=event_timestamp_ms,
        active=active,
    ):
        current_tier = "pro" if any(
            pid in pro_product_ids and bool(entry.get("active"))
            for pid, entry in states.items()
        ) else "free"
        return True, current_tier

    states[product_id] = {
        "active": active,
        "event_timestamp_ms": event_timestamp_ms,
        "event_id": event_id,
    }
    state.product_states_json = json.dumps(states, sort_keys=True, separators=(",", ":"))
    state.updated_at = _utcnow()

    resulting_tier = "pro" if any(
        pid in pro_product_ids and bool(entry.get("active"))
        for pid, entry in states.items()
    ) else "free"
    return False, resulting_tier


def _apply_bonus(
    row: UserModel,
    *,
    bonus_delta: int,
) -> int | None:
    if not bonus_delta:
        return None
    row.bonus_analyses = int(row.bonus_analyses or 0) + bonus_delta
    return row.bonus_analyses


def apply_revenuecat_mutation(
    *,
    event_id: str,
    candidate_user_ids: Iterable[str],
    rc_customer_id: str | None,
    bonus_delta: int = 0,
    entitlement_product_id: str | None = None,
    entitlement_active: bool | None = None,
    pro_product_ids: Iterable[str] = (),
    event_timestamp_ms: int | None = None,
) -> RevenueCatMutationResult:
    """Apply one RevenueCat billing mutation exactly once.

    The event-id claim, user mutation, per-product ordering state, and bonus update
    share one transaction. Unknown users roll the claim back so RevenueCat can retry.
    Stale events commit only their event-id claim and never change user state.
    """
    eid = (event_id or "").strip()
    product_id = (entitlement_product_id or "").strip()
    allowed_products = set(_normalized_candidates(pro_product_ids))

    if not eid:
        raise ValueError("RevenueCat event id is required")
    has_entitlement_mutation = bool(product_id) and entitlement_active is not None
    if not has_entitlement_mutation and bonus_delta == 0:
        raise ValueError("RevenueCat mutation requires an entitlement change or bonus delta")
    if bool(product_id) != (entitlement_active is not None):
        raise ValueError("RevenueCat entitlement product and active state must be provided together")
    if has_entitlement_mutation and product_id not in allowed_products:
        raise ValueError("RevenueCat entitlement product is not allowlisted")
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
                session.rollback()
                return RevenueCatMutationResult(duplicate=False, user_id=None)

            resulting_tier: str | None = None
            if has_entitlement_mutation:
                state = _locked_entitlement_state(session, row.id)
                stale, resulting_tier = _apply_product_entitlement_event(
                    state,
                    product_id=product_id,
                    active=bool(entitlement_active),
                    event_timestamp_ms=event_timestamp_ms,
                    event_id=eid,
                    pro_product_ids=allowed_products,
                )
                if stale:
                    # Keep the stale event deduplicated, but do not alter the user or
                    # the stored product state.
                    session.commit()
                    return RevenueCatMutationResult(
                        duplicate=False,
                        user_id=row.id,
                        tier=resulting_tier,
                        stale=True,
                    )
                row.tier = resulting_tier
                session.add(state)

            bonus_total = _apply_bonus(row, bonus_delta=bonus_delta)
            rc_id = (rc_customer_id or "").strip()
            if rc_id:
                row.rc_customer_id = rc_id
            session.add(row)

            session.commit()
            return RevenueCatMutationResult(
                duplicate=False,
                user_id=row.id,
                bonus_total=bonus_total,
                tier=resulting_tier,
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
