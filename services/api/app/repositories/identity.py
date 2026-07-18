"""Identity repository: users, sessions, feedback, webhook dedup (Postgres via SQLModel)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlmodel import select

from app.core.admin import promote_admin_if_eligible
from app.models import (
    BetaFeedbackModel,
    ClientFunnelEventModel,
    ClipModel,
    ConsentEventModel,
    CustomLineModel,
    FeedEventModel,
    LineAttemptModel,
    MilestoneModel,
    RcWebhookDedupModel,
    SessionAttemptModel,
    SessionModel,
    SkateSessionModel,
    TrickStatModel,
    UserModel,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# Expired trials land on free_expired (feed-only) once upload/session gates enforce
# tier_has_feature — see clips_v1.py and sessions.py.
_TRIAL_EXPIRY_TARGET_TIER = "free_expired"


class IdentityRepository:
    """
    Postgres-backed identity store.
    API-compatible with the old identity store so callers can swap with minimal changes.
    Accepts a session_factory callable that returns a SQLModel Session context manager.
    """

    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def init_schema(self) -> None:
        pass

    def create_user_session(self, email: str) -> tuple[str, str, str]:
        """Return (user_id, session_token, normalized_email)."""
        norm = email.strip().lower()
        if not norm or "@" not in norm:
            raise ValueError("invalid email")
        uid = str(uuid.uuid4())
        token = uuid.uuid4().hex + uuid.uuid4().hex
        now = _utcnow()
        with self._sf() as session:
            stmt = select(UserModel).where(UserModel.email == norm)
            existing = session.exec(stmt).first()
            if existing:
                uid = existing.id
                if promote_admin_if_eligible(existing, source="email_session", session=session):
                    session.add(existing)
            else:
                session.add(
                    UserModel(
                        id=uid,
                        email=norm,
                        created_at=now,
                    )
                )
            session.add(SessionModel(token=token, user_id=uid, created_at=now))
            session.commit()
        return uid, token, norm

    def initialize_trial_for_new_user(self, user_id: str) -> None:
        now = _utcnow()
        expires_at = now + timedelta(days=7)
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row is None:
                return
            if row.trial_started_at is not None or row.trial_expires_at is not None:
                return
            row.tier = "trial"
            row.trial_started_at = now
            row.trial_expires_at = expires_at
            if not (row.subscription_status or "").strip():
                row.subscription_status = "active"
            session.add(row)
            session.commit()

    def validate_token(self, token: str | None) -> str | None:
        if not token or len(token) < 8:
            return None
        with self._sf() as session:
            row = session.get(SessionModel, token.strip())
            if row is None:
                return None
            user = session.get(UserModel, row.user_id)
            if user and user.tokens_invalidated_at is not None:
                inv = user.tokens_invalidated_at
                if inv.tzinfo is None:
                    inv = inv.replace(tzinfo=timezone.utc)
                sess_ct = row.created_at
                if sess_ct.tzinfo is None:
                    sess_ct = sess_ct.replace(tzinfo=timezone.utc)
                if sess_ct < inv:
                    return None
            return row.user_id

    def user_exists(self, user_id: str) -> bool:
        with self._sf() as session:
            return session.get(UserModel, user_id) is not None

    def _expire_trial_if_due(self, session, row) -> bool:
        """
        If this user's trial window has passed, downgrade in place.

        Called lazily from get_user_tier so no scheduler or cron is required:
        every quota decision (clip_quota.reserve_clip_submission,
        clip_v1_pipeline, /account/me, billing_sync) reads the tier through
        get_user_tier, so an expired trial is downgraded on its next request.

        Returns True when a downgrade happened (caller must commit).
        Timezone-naive timestamps (SQLite dev) are treated as UTC to match the
        rest of the app.
        """
        if row is None or (row.tier or "").strip().lower() != "trial":
            return False
        expires = row.trial_expires_at
        if expires is None:
            # Trial tier without an expiry window — fail toward the paid funnel.
            expires = _utcnow()
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires > _utcnow():
            return False

        from app.models import SubscriptionEventModel

        row.tier = _TRIAL_EXPIRY_TARGET_TIER
        row.subscription_status = "expired"
        session.add(row)
        session.add(
            SubscriptionEventModel(
                user_id=row.id,
                event_type="trial_expired",
                from_tier="trial",
                to_tier=_TRIAL_EXPIRY_TARGET_TIER,
                occurred_at=_utcnow(),
            )
        )
        return True

    def get_user_tier(self, user_id: str) -> str:
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row is None:
                return "free"
            if self._expire_trial_if_due(session, row):
                session.commit()
            return row.tier

    def ensure_invite_claim_user(self, user_id: str, tier: str) -> None:
        synthetic = f"invite-{user_id}@beta.onflow.internal"
        now = _utcnow()
        with self._sf() as session:
            existing = session.get(UserModel, user_id)
            if existing:
                existing.tier = tier
                existing.auth_provider = "invite"
                session.add(existing)
            else:
                session.add(
                    UserModel(
                        id=user_id,
                        email=synthetic,
                        tier=tier,
                        auth_provider="invite",
                        created_at=now,
                    )
                )
            session.commit()

    def set_user_tier(self, user_id: str, tier: str, rc_customer_id: str | None = None) -> None:
        rc = (rc_customer_id or "").strip() or None
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row is None:
                return
            row.tier = tier
            if rc:
                row.rc_customer_id = rc
            session.add(row)
            session.commit()

    def get_user_by_rc_customer(self, rc_customer_id: str) -> str | None:
        rc = (rc_customer_id or "").strip()
        if not rc:
            return None
        with self._sf() as session:
            stmt = select(UserModel).where(UserModel.rc_customer_id == rc)
            row = session.exec(stmt).first()
            return row.id if row else None

    def get_user_by_google_sub(self, sub: str) -> UserModel | None:
        s = (sub or "").strip()
        if not s:
            return None
        with self._sf() as session:
            stmt = select(UserModel).where(UserModel.google_sub == s)
            return session.exec(stmt).first()

    def get_user_by_apple_sub(self, sub: str) -> UserModel | None:
        s = (sub or "").strip()
        if not s:
            return None
        with self._sf() as session:
            stmt = select(UserModel).where(UserModel.apple_sub == s)
            return session.exec(stmt).first()

    def get_user_by_email_ci(self, email: str) -> UserModel | None:
        norm = email.strip().lower()
        if not norm or "@" not in norm:
            return None
        with self._sf() as session:
            stmt = select(UserModel).where(func.lower(UserModel.email) == norm)
            return session.exec(stmt).first()

    def oauth_complete_signin(
        self,
        *,
        provider: str,
        sub: str,
        email: str | None,
        email_verified: bool,
    ) -> tuple[str, bool]:
        """
        Upsert user after provider token verification.
        Returns (user_id, is_new_user). New users receive one OAuth signup bonus (granted/used columns).
        Linking to an existing invite or email account does not grant the signup bonus.
        """
        sub = sub.strip()
        if not sub:
            raise ValueError("missing subject")

        email_norm = email.strip().lower() if email and str(email).strip() else None

        with self._sf() as session:
            row: UserModel | None = None
            if provider == "google":
                row = session.exec(select(UserModel).where(UserModel.google_sub == sub)).first()
            elif provider == "apple":
                row = session.exec(select(UserModel).where(UserModel.apple_sub == sub)).first()
            else:
                raise ValueError("invalid provider")

            if row is None and email_norm:
                row = session.exec(
                    select(UserModel).where(func.lower(UserModel.email) == email_norm)
                ).first()

            if row:
                if provider == "google":
                    row.google_sub = sub
                else:
                    row.apple_sub = sub
                if email_norm:
                    row.email = email_norm
                if row.auth_provider != "invite" and not (row.auth_provider or "").strip():
                    row.auth_provider = provider
                row.email_verified = bool(email_verified) or bool(row.email_verified)
                promote_admin_if_eligible(row, source=f"oauth_{provider}", session=session)
                session.add(row)
                session.commit()
                return row.id, False

            if not email_norm and provider == "apple":
                email_norm = f"apple-{sub[:48]}@oauth-placeholder.onflow.internal"

            if not email_norm:
                raise ValueError("email required for new Google user")

            uid = str(uuid.uuid4())
            new_user = UserModel(
                id=uid,
                email=email_norm,
                tier="free",
                auth_provider=provider,
                google_sub=sub if provider == "google" else None,
                apple_sub=sub if provider == "apple" else None,
                email_verified=bool(email_verified),
                bonus_analyses_granted=1,
                bonus_analyses_used=0,
                created_at=_utcnow(),
            )
            session.add(new_user)
            session.flush()
            promote_admin_if_eligible(new_user, source=f"oauth_{provider}", session=session)
            session.add(new_user)
            session.commit()
            return uid, True

    def get_bonus_analyses(self, user_id: str) -> int:
        """Total bonus credits: purchased pool plus OAuth signup bonus remaining."""
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if not row:
                return 0
            purchase = row.bonus_analyses or 0
            oauth_rem = max(
                0,
                (row.bonus_analyses_granted or 0) - (row.bonus_analyses_used or 0),
            )
            return purchase + oauth_rem

    def try_consume_one_bonus(self, user_id: str) -> bool:
        """
        After monthly free quota is exhausted, consume one credit from the OAuth signup
        pool first, then from purchased bonus_analyses.
        """
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if not row:
                return False
            granted = row.bonus_analyses_granted or 0
            used = row.bonus_analyses_used or 0
            if granted > used:
                row.bonus_analyses_used = used + 1
                session.add(row)
                session.commit()
                return True
            if (row.bonus_analyses or 0) > 0:
                row.bonus_analyses = (row.bonus_analyses or 0) - 1
                session.add(row)
                session.commit()
                return True
            return False

    def decrement_bonus_analyses(self, user_id: str) -> int:
        """Legacy: decrement purchased bonus pool only (not OAuth signup pool)."""
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if not row or (row.bonus_analyses or 0) <= 0:
                return 0
            row.bonus_analyses = (row.bonus_analyses or 0) - 1
            session.add(row)
            session.commit()
            return row.bonus_analyses

    def add_bonus_analyses(self, user_id: str, n: int) -> int:
        if n <= 0:
            return self.get_bonus_analyses(user_id)
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if not row:
                return 0
            row.bonus_analyses = (row.bonus_analyses or 0) + n
            session.add(row)
            session.commit()
            return row.bonus_analyses

    def refund_one_bonus(self, user_id: str) -> bool:
        """
        Best-effort reverse of ``try_consume_one_bonus``.

        Prefer restoring the OAuth signup pool (decrement ``bonus_analyses_used``);
        otherwise credit the purchased pool. Used when enqueue fails after charge.
        """
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if not row:
                return False
            used = row.bonus_analyses_used or 0
            if used > 0:
                row.bonus_analyses_used = used - 1
                session.add(row)
                session.commit()
                return True
            row.bonus_analyses = (row.bonus_analyses or 0) + 1
            session.add(row)
            session.commit()
            return True

    def set_clip_retention_consent(self, user_id: str, consent: bool) -> dict[str, Any]:
        now = _utcnow() if consent else None
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row:
                row.clip_retention_consent = consent
                row.clip_retention_consent_at = now
                session.add(row)
            elif consent:
                synthetic = f"retention-{user_id}@beta.onflow.internal"
                row = UserModel(
                    id=user_id,
                    email=synthetic,
                    clip_retention_consent=True,
                    clip_retention_consent_at=now,
                    created_at=_utcnow(),
                )
                session.add(row)
            session.commit()
            if row:
                return {
                    "consent": row.clip_retention_consent,
                    "consent_at": _iso(row.clip_retention_consent_at) if row.clip_retention_consent_at else None,
                }
            return {"consent": False, "consent_at": None}

    def set_profile_image_url(self, user_id: str, profile_image_url: str | None) -> str | None:
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row is None:
                return None
            row.profile_image_url = profile_image_url
            session.add(row)
            session.commit()
            return row.profile_image_url

    def get_clip_retention_consent(self, user_id: str) -> bool:
        return self.get_clip_retention_state(user_id)["consent"]

    def get_clip_retention_state(self, user_id: str) -> dict[str, Any]:
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if not row:
                return {"consent": False, "consent_at": None}
            return {
                "consent": bool(row.clip_retention_consent),
                "consent_at": _iso(row.clip_retention_consent_at) if row.clip_retention_consent_at else None,
            }

    def feedback_insert(
        self,
        *,
        user_id: str | None,
        job_id: str | None,
        useful: bool | None,
        accurate: bool | None,
        issue_kind: str | None,
        note: str,
        client_kind: str | None,
        coaching_helped_next_try: bool | None = None,
        coaching_too_generic: bool | None = None,
        coaching_wrong_read: bool | None = None,
        best_cue_clear: bool | None = None,
    ) -> str:
        fid = uuid.uuid4().hex[:16]
        row = BetaFeedbackModel(
            id=fid,
            user_id=user_id,
            job_id=job_id,
            useful=useful,
            accurate=accurate,
            issue_kind=issue_kind,
            note=note or "",
            client_kind=client_kind,
            coaching_helped_next_try=coaching_helped_next_try,
            coaching_too_generic=coaching_too_generic,
            coaching_wrong_read=coaching_wrong_read,
            best_cue_clear=best_cue_clear,
            created_at=_utcnow(),
        )
        with self._sf() as session:
            session.add(row)
            session.commit()
        return fid

    def feedback_coaching_quality_metrics(self, user_id: str) -> dict[str, Any]:
        with self._sf() as session:
            base = select(BetaFeedbackModel).where(BetaFeedbackModel.user_id == user_id)
            all_rows = list(session.exec(base))
            total = len(all_rows)

            def _count(attr: str, val: bool = True) -> int:
                return sum(1 for r in all_rows if getattr(r, attr, None) is val)

            useful_count = _count("useful")
            too_generic_count = _count("coaching_too_generic")
            wrong_read_count = _count("coaching_wrong_read")
            helped_next_try_count = _count("coaching_helped_next_try")
            cue_clear_count = _count("best_cue_clear")

            def _rate(num: int) -> float:
                return round(num / total, 4) if total else 0.0

            by_kind: dict[str, int] = {}
            for r in all_rows:
                k = r.issue_kind or "unset"
                by_kind[k] = by_kind.get(k, 0) + 1
            by_issue_kind = sorted(
                [{"issue_kind": k, "count": v} for k, v in by_kind.items()],
                key=lambda x: x["count"],
                reverse=True,
            )

            recent_stmt = (
                select(BetaFeedbackModel)
                .where(BetaFeedbackModel.user_id == user_id)
                .order_by(BetaFeedbackModel.created_at.desc())
                .limit(20)
            )
            recent_rows = list(session.exec(recent_stmt))
            recent_flags = [
                {
                    "feedback_id": r.id,
                    "job_id": r.job_id,
                    "issue_kind": r.issue_kind,
                    "useful": r.useful,
                    "coaching_helped_next_try": r.coaching_helped_next_try,
                    "coaching_too_generic": r.coaching_too_generic,
                    "coaching_wrong_read": r.coaching_wrong_read,
                    "best_cue_clear": r.best_cue_clear,
                    "created_at": _iso(r.created_at),
                }
                for r in recent_rows
            ]

        return {
            "total_feedback": total,
            "useful_count": useful_count,
            "too_generic_count": too_generic_count,
            "wrong_read_count": wrong_read_count,
            "helped_next_try_count": helped_next_try_count,
            "cue_clear_count": cue_clear_count,
            "useful_rate": _rate(useful_count),
            "too_generic_rate": _rate(too_generic_count),
            "wrong_read_rate": _rate(wrong_read_count),
            "helped_next_try_rate": _rate(helped_next_try_count),
            "cue_clear_rate": _rate(cue_clear_count),
            "by_issue_kind": by_issue_kind,
            "recent_flags": recent_flags,
        }

    def try_record_rc_webhook_event(self, event_id: str) -> bool:
        eid = (event_id or "").strip()
        if not eid:
            return True
        with self._sf() as session:
            existing = session.get(RcWebhookDedupModel, eid)
            if existing:
                return False
            session.add(RcWebhookDedupModel(event_id=eid, created_at=_utcnow()))
            session.commit()
            return True

    def record_funnel_event(
        self,
        user_id: str,
        kind: str,
        *,
        job_id: str | None = None,
        share_target: str | None = None,
        error_detail: str | None = None,
        ref_source: str | None = None,
    ) -> None:
        """Persist client funnel rows (share flow, etc.) for admin aggregates."""
        jid = job_id.strip() if job_id and job_id.strip() else None
        with self._sf() as session:
            session.add(
                ClientFunnelEventModel(
                    user_id=user_id,
                    kind=kind,
                    job_id=jid,
                    share_target=(share_target.strip() if share_target else None),
                    error_detail=(error_detail[:2000] if error_detail else None),
                    ref_source=(ref_source.strip() if ref_source else None),
                )
            )
            session.commit()

    def share_funnel_counts_since(self, since: datetime) -> dict[str, int]:
        """Counts per share-related kind since ``since`` (UTC)."""
        kinds = (
            "share_initiated",
            "share_completed",
            "share_failed",
            "share_install_attributed",
        )
        out: dict[str, int] = {k: 0 for k in kinds}
        with self._sf() as session:
            for k in kinds:
                stmt = select(func.count(ClientFunnelEventModel.id)).where(
                    ClientFunnelEventModel.kind == k,
                    ClientFunnelEventModel.created_at >= since,
                )
                n = session.exec(stmt).one()
                out[k] = int(n)
        return out

    def get_user(self, user_id: str) -> UserModel | None:
        with self._sf() as session:
            return session.get(UserModel, user_id)

    def delete_sessions_for_user(self, user_id: str) -> None:
        with self._sf() as session:
            for row in session.exec(select(SessionModel).where(SessionModel.user_id == user_id)):
                session.delete(row)
            session.commit()

    def grant_consent(
        self,
        user_id: str,
        *,
        copy_version: str,
        source: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserModel:
        now = _utcnow()
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row is None:
                raise ValueError("user not found")
            row.consent_granted_at = now
            row.consent_copy_version = copy_version[:32]
            row.consent_source = source[:32]
            session.add(row)
            session.add(
                ConsentEventModel(
                    user_id=user_id,
                    event_type="grant",
                    copy_version=copy_version[:32],
                    source=source[:32],
                    occurred_at=now,
                    ip_address=(ip_address or "")[:45] if ip_address else None,
                    user_agent=(user_agent or "")[:512] if user_agent else None,
                )
            )
            session.commit()
            session.refresh(row)
            return row

    def list_consent_events(self, user_id: str) -> list[dict[str, Any]]:
        with self._sf() as session:
            stmt = (
                select(ConsentEventModel)
                .where(ConsentEventModel.user_id == user_id)
                .order_by(ConsentEventModel.occurred_at.desc())
            )
            rows = list(session.exec(stmt))
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "id": r.id,
                        "event_type": r.event_type,
                        "copy_version": r.copy_version,
                        "source": r.source,
                        "occurred_at": _iso(r.occurred_at),
                        "ip_address": r.ip_address,
                        "user_agent": r.user_agent,
                    }
                )
            return out

    def purge_user_owned_rows(self, user_id: str) -> None:
        """Remove user-owned rows except users and consent_events."""
        with self._sf() as session:
            for row in session.exec(select(FeedEventModel).where(FeedEventModel.user_id == user_id)):
                session.delete(row)
            # Attempts reference skate_sessions — delete before sessions.
            for row in session.exec(
                select(SessionAttemptModel).where(SessionAttemptModel.user_id == user_id)
            ):
                session.delete(row)
            for row in session.exec(select(ClipModel).where(ClipModel.user_id == user_id)):
                session.delete(row)
            for row in session.exec(
                select(SkateSessionModel).where(SkateSessionModel.user_id == user_id)
            ):
                session.delete(row)
            for row in session.exec(select(TrickStatModel).where(TrickStatModel.user_id == user_id)):
                session.delete(row)
            for row in session.exec(select(MilestoneModel).where(MilestoneModel.user_id == user_id)):
                session.delete(row)
            for row in session.exec(select(CustomLineModel).where(CustomLineModel.user_id == user_id)):
                session.delete(row)
            for row in session.exec(select(LineAttemptModel).where(LineAttemptModel.user_id == user_id)):
                session.delete(row)
            for row in session.exec(
                select(BetaFeedbackModel).where(BetaFeedbackModel.user_id == user_id)
            ):
                session.delete(row)
            for row in session.exec(
                select(ClientFunnelEventModel).where(ClientFunnelEventModel.user_id == user_id)
            ):
                session.delete(row)
            session.commit()

    def anonymize_user_for_deletion(self, user_id: str) -> UserModel | None:
        now = _utcnow()
        with self._sf() as session:
            row = session.get(UserModel, user_id)
            if row is None:
                return None
            row.email = f"deleted-user-{user_id}@onflow.invalid"
            row.pending_deletion_at = now
            row.deletion_source = "user"
            row.tokens_invalidated_at = now
            row.google_sub = None
            row.apple_sub = None
            row.profile_image_url = None
            session.add(row)
            session.commit()
            session.refresh(row)
            return row
