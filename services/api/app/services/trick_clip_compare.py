"""Trick clip comparison (Step 5G).

Compares the owner's **oldest** and **newest** analyzed clips for a single trick.
Uses ``clips`` rows (V1) plus optional ``trick_stats`` coaching fields on those jobs.
Progress notes are built only from stored data — never fabricated coaching copy.
"""
from __future__ import annotations

from datetime import timezone

from sqlmodel import Session, select

from app.models import ClipModel, TrickStatModel
from app.schemas.trick_compare import TrickClipCompareResponse, TrickCompareClip
from app.services.clip_upload import iso_z
from app.services.trick_registry import normalize_trick_name, resolve_trick


def _playback_url(storage_url: str | None) -> str | None:
    url = (storage_url or "").strip()
    return url or None


def _clip_matches_trick(clip: ClipModel, trick_key: str) -> bool:
    if not clip.trick_id or not clip.trick_id.strip():
        return False
    return normalize_trick_name(clip.trick_id) == trick_key


def _clip_to_compare_item(clip: ClipModel) -> TrickCompareClip:
    display_trick = normalize_trick_name(clip.trick_id) if clip.trick_id else None
    return TrickCompareClip(
        clip_id=clip.id,
        session_id=clip.session_id,
        thumbnail_url=clip.thumbnail_url,
        video_playback_url=_playback_url(clip.storage_url),
        pte_score=clip.pte_rating,
        landed=clip.landed,
        created_at=iso_z(clip.created_at),
    )


def _stat_for_job(db: Session, job_id: str, user_id: str) -> TrickStatModel | None:
    return db.exec(
        select(TrickStatModel).where(
            TrickStatModel.job_id == job_id,
            TrickStatModel.user_id == user_id,
        )
    ).first()


def _build_progress_notes(
    oldest: ClipModel,
    newest: ClipModel,
    *,
    oldest_stat: TrickStatModel | None,
    newest_stat: TrickStatModel | None,
    pte_delta: int | None,
) -> list[str]:
    notes: list[str] = []

    if pte_delta is not None and pte_delta > 0:
        notes.append(
            f"PTE improved from {oldest.pte_rating} to {newest.pte_rating}."
        )
    elif pte_delta is not None and pte_delta < 0:
        notes.append(
            f"PTE changed from {oldest.pte_rating} to {newest.pte_rating}."
        )

    if oldest.landed is False and newest.landed is True:
        notes.append("Latest clip is marked landed; the earlier clip was not.")
    elif oldest.landed is not True and newest.landed is True:
        notes.append("You landed it on the latest attempt.")

    if newest_stat and newest_stat.best_cue and newest_stat.best_cue.strip():
        cue = newest_stat.best_cue.strip()
        old_cue = (oldest_stat.best_cue or "").strip() if oldest_stat else ""
        if cue != old_cue:
            notes.append(f"Latest coaching cue: {cue}")

    if (
        newest_stat
        and newest_stat.primary_issue_label
        and oldest_stat
        and oldest_stat.primary_issue_label
        and newest_stat.primary_issue_key != oldest_stat.primary_issue_key
    ):
        notes.append(
            f"Focus shifted from {oldest_stat.primary_issue_label} "
            f"to {newest_stat.primary_issue_label}."
        )

    if newest_stat and newest_stat.review_readiness == "usable":
        if oldest_stat and oldest_stat.review_readiness in ("limited", "insufficient"):
            notes.append("Latest clip review readiness is stronger than the earlier one.")

    return notes[:5]


def build_trick_clip_compare(
    db: Session, user_id: str, trick_name: str
) -> TrickClipCompareResponse | None:
    """Return comparison payload, or ``None`` when the user has no clips for this trick."""
    trick_key = normalize_trick_name(trick_name)
    if not trick_key:
        return None

    entry = resolve_trick(trick_name)
    trick_display = entry.name if entry else trick_name.strip().title()

    rows = list(
        db.exec(
            select(ClipModel)
            .where(
                ClipModel.user_id == user_id,
                ClipModel.deleted_at.is_(None),  # type: ignore[union-attr]
                ClipModel.upload_status == "analyzed",
            )
            .order_by(ClipModel.created_at.asc())
        )
    )
    matching = [c for c in rows if _clip_matches_trick(c, trick_key)]
    if not matching:
        return None

    oldest = matching[0]
    newest = matching[-1]
    clips_count = len(matching)

    if clips_count < 2:
        return TrickClipCompareResponse(
            trick_name=trick_key,
            trick_display=trick_display,
            compare_available=False,
            newest_clip=_clip_to_compare_item(newest),
            clips_count=clips_count,
            progress_notes=[],
        )

    oldest_dt = oldest.created_at
    newest_dt = newest.created_at
    if oldest_dt.tzinfo is None:
        oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
    if newest_dt.tzinfo is None:
        newest_dt = newest_dt.replace(tzinfo=timezone.utc)
    days_between = max(0, (newest_dt - oldest_dt).days)

    pte_delta: int | None = None
    if oldest.pte_rating is not None and newest.pte_rating is not None:
        pte_delta = newest.pte_rating - oldest.pte_rating

    oldest_stat = _stat_for_job(db, oldest.id, user_id)
    newest_stat = _stat_for_job(db, newest.id, user_id)

    return TrickClipCompareResponse(
        trick_name=trick_key,
        trick_display=trick_display,
        compare_available=True,
        days_between=days_between,
        pte_delta=pte_delta,
        oldest_landed=oldest.landed,
        newest_landed=newest.landed,
        oldest_clip=_clip_to_compare_item(oldest),
        newest_clip=_clip_to_compare_item(newest),
        progress_notes=_build_progress_notes(
            oldest,
            newest,
            oldest_stat=oldest_stat,
            newest_stat=newest_stat,
            pte_delta=pte_delta,
        ),
        clips_count=clips_count,
    )
