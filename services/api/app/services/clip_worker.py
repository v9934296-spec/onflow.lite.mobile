"""
Background clip job processing.

Completed jobs normally include full Gemini analysis. When the main Gemini pipeline
raises `GeminiPipelineError`, we still complete the job with an honest degraded payload
(automated video pass only — no fabricated mechanics review).
Video first-pass is used for readability checks and container metrics.
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from sqlmodel import Session

from app.core.config import get_settings
from app.core.resilience import gemini_circuit
from app.core.tiers import (
    normalize_tier,
    normalized_review_model_for_provider,
    resolve_analysis_provider_for_tier,
    resolve_gemini_model_for_tier,
)
from app.repositories.clip_jobs import ClipJobRepository
from app.schemas.gemini_analysis import GeminiClipAnalysis
from app.services.beta_observability import log_beta
from app.services.clip_retention import retain_clip
from app.services.clip_playback_hints import merge_playback_hints_into_result
from app.services.clip_quota import (
    begin_quota_release,
    identity_repository_for_worker,
    settle_quota_release,
)
from app.services.clip_review_assembly import (
    build_completed_result_from_gemini,
    build_degraded_provider_failure_result,
)
from app.services.gemini_spend_cap import record_gemini_call
from app.services.gemini_clip_analyzer import (
    GeminiPipelineError,
    analyze_clip_with_gemini,
    guess_clip_mime,
)
from app.services.gemini_prompt_tier import build_tier_aware_prompt
from app.services.gemini_prompt import ClipAnalysisMetadata
from app.services.gemini_reviewer import GeminiReviewer
from app.services.twelvelabs_clip_analyzer import analyze_clip_with_twelvelabs
from app.services.twelvelabs_reviewer import TwelveLabsReviewer
from app.services.landing_status import resolve_landed_status
from app.services.line_matching import record_matching_line_attempts
from app.services.session_grouping import resolve_session_id
from app.services.stats_logic import (
    build_attempt_compare_block,
    build_session_recap_payload,
    fetch_prior_trick_stats,
)
from app.services.trick_registry import normalize_trick_name, resolve_trick
from app.services.video_first_pass import analyze_video_first_pass
from app.services.video_signature import looks_like_video

logger = structlog.get_logger(__name__)

FAILURE_VIDEO_UNREADABLE = "video_unreadable"
UPLOAD_MISSING = "upload_missing"
FAILURE_CLIP_QUALITY_INSUFFICIENT = "clip_quality_insufficient"

# A completed job keeps its charge only when the skater actually received a
# usable read. "insufficient" covers both a degraded provider failure and
# footage the engine could not assess, and neither is something to bill for
# (spec decision 17). Abuse is bounded separately by the hourly/daily analysis
# caps and the per-user concurrency limit, not by charging for non-answers.
CHARGEABLE_READINESS = frozenset({"usable", "limited"})

# Gemini result cache: keyed by content SHA-256 + tier. 30-day TTL. Best-effort —
# silently disabled when Redis is unavailable. Saves ~30-45s and one Gemini call
# on identical re-uploads (same user retry, or same file from different users).
_GEMINI_CACHE_TTL_SECONDS = 30 * 86_400
_redis_async_client: object | None = None
_redis_async_init_failed = False


async def _get_async_redis() -> object | None:
    """Lazy-init an async Redis client for the worker process. Returns None if not configured."""
    global _redis_async_client, _redis_async_init_failed
    if _redis_async_client is not None:
        return _redis_async_client
    if _redis_async_init_failed:
        return None
    redis_url = (get_settings().redis_url or "").strip()
    if not redis_url:
        _redis_async_init_failed = True
        return None
    try:
        import redis.asyncio as aioredis  # type: ignore[import]

        _redis_async_client = aioredis.from_url(
            redis_url, decode_responses=True, socket_timeout=1.0
        )
        return _redis_async_client
    except Exception:
        _redis_async_init_failed = True
        return None


def _gemini_cache_key(content_sha256: str, tier: str) -> str:
    return f"onflow:gemini:{content_sha256}:{tier or 'free'}"


async def _gemini_cache_get(
    content_sha256: str, tier: str
) -> GeminiClipAnalysis | None:
    if not content_sha256:
        return None
    r = await _get_async_redis()
    if r is None:
        return None
    try:
        raw = await r.get(_gemini_cache_key(content_sha256, tier))  # type: ignore[attr-defined]
        if not raw:
            return None
        return GeminiClipAnalysis.model_validate_json(raw)
    except Exception:
        return None


async def _gemini_cache_set(
    content_sha256: str, tier: str, analysis: GeminiClipAnalysis
) -> None:
    if not content_sha256:
        return
    r = await _get_async_redis()
    if r is None:
        return
    try:
        await r.set(  # type: ignore[attr-defined]
            _gemini_cache_key(content_sha256, tier),
            analysis.model_dump_json(),
            ex=_GEMINI_CACHE_TTL_SECONDS,
        )
    except Exception:
        pass


def _maybe_attach_attempt_compare(
    result: dict[str, Any],
    *,
    user_id: str,
    job_id: str,
    tricks_raw: list[Any],
) -> None:
    """
    Same-user, same-trick compare vs up to 3 prior TrickStat rows. Non-fatal on failure.
    """
    try:
        uid = (user_id or "").strip()
        if not uid or not tricks_raw:
            return
        t0 = tricks_raw[0]
        if not isinstance(t0, str) or not t0.strip():
            return
        from app.core.database import get_engine

        tn = normalize_trick_name(t0)
        entry = resolve_trick(t0)
        t_display = entry.name if entry else t0.strip()
        engine = get_engine()
        with Session(engine) as session:
            priors = fetch_prior_trick_stats(session, uid, tn, job_id)
        if not priors:
            return
        latest_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        block = build_attempt_compare_block(
            trick_display_name=t_display,
            trick_name_normalized=tn,
            job_id=job_id,
            latest_result=result,
            latest_created_at_iso=latest_iso,
            previous_rows=priors,
        )
        if block and block.get("compare_available"):
            result["attempt_compare"] = block
    except Exception:
        logger.warning("attempt_compare_not_attached", exc_info=True)


def _maybe_attach_session_recap(
    result: dict[str, Any],
    *,
    user_id: str | None,
    job_id: str,
    tricks_raw: list[Any],
) -> None:
    """
    Same-user session pattern recap from TrickStat rows. Non-fatal; skipped without auth or tricks.
    """
    uid = (user_id or "").strip()
    if not uid or not tricks_raw:
        return
    try:
        from sqlmodel import Session, select

        from app.core.database import get_engine
        from app.models import TrickStatModel

        engine = get_engine()
        with Session(engine) as session:
            job_rows = list(
                session.exec(
                    select(TrickStatModel).where(
                        TrickStatModel.user_id == uid,
                        TrickStatModel.job_id == job_id,
                    )
                )
            )
            if not job_rows:
                return
            sid = job_rows[0].session_id
            if not sid:
                return
            rows = list(
                session.exec(
                    select(TrickStatModel)
                    .where(
                        TrickStatModel.user_id == uid,
                        TrickStatModel.session_id == sid,
                    )
                    .order_by(TrickStatModel.created_at)
                )
            )
        recap = build_session_recap_payload(sid, rows)
        result["session_recap"] = recap
    except Exception:
        logger.warning("session_recap_not_attached", exc_info=True)


async def _cleanup_upload(
    file_path: str | Path,
    storage_key: str = "",
    *,
    skip_remote_delete: bool = False,
) -> None:
    """Delete the uploaded video from storage after processing. Non-fatal if it fails."""
    # Clean local temp file if it exists
    try:
        p = Path(file_path) if not isinstance(file_path, Path) else file_path
        if p.is_file():
            p.unlink()
            logger.info("Cleaned up local file: %s", p.name)
    except OSError:
        logger.warning("Could not clean up local file", file_path=str(file_path), exc_info=True)

    # Clean object storage (skipped when blobs must persist for playback links).
    if storage_key and not skip_remote_delete:
        try:
            from app.services.object_storage import build_storage
            storage = build_storage()
            await storage.delete(storage_key)
        except Exception:
            logger.warning("Could not clean up storage key=%s", storage_key, exc_info=True)


def _sync_v1_clip_terminal(
    job_id: str,
    *,
    failed: bool,
    result: dict[str, Any] | None = None,
) -> None:
    from app.services.clip_v1_pipeline import sync_v1_clip_from_job_result

    sync_v1_clip_from_job_result(job_id, result, failed=failed)


def _release_quota_and_persist(
    repo: ClipJobRepository,
    job: Any,
    *,
    claim_token: str | None,
    reason: str,
) -> bool:
    """Give the analysis slot back, then persist the terminal job in one write.

    A skater is charged when a clip is accepted for analysis. If no usable
    analysis comes back, the charge is reversed — spec decision 17. The release
    marker rides along on the same job update that records the terminal state,
    so a lost claim cannot leave a refunded credit attached to a job row that
    still looks charged.
    """
    release = begin_quota_release(job)
    persisted = _persist_claimed(repo, job, claim_token=claim_token)
    if not persisted:
        # Another worker owns this job now; it will run its own release.
        return False
    if release.changed:
        logger.info(
            "event=clip_quota_released job_id=%s reason=%s source=%s",
            getattr(job, "id", ""),
            reason,
            job.quota_source,
        )
        settle_quota_release(
            identity_repository_for_worker(),
            job.user_id,
            release,
            job_id=getattr(job, "id", ""),
            reason=reason,
        )
    return True


def _persist_claimed(repo: ClipJobRepository, job: Any, *, claim_token: str | None) -> bool:
    """Write terminal/in-flight job state only while ``claim_token`` still owns it."""
    if not claim_token:
        repo.update(job)
        return True
    update_claimed = getattr(repo, "update_claimed", None)
    if callable(update_claimed):
        ok = bool(update_claimed(job, claim_token=claim_token))
        if not ok:
            logger.warning(
                "event=clip_job_update_rejected reason=lost_claim job_id=%s",
                getattr(job, "id", ""),
            )
        return ok
    repo.update(job)
    return True


async def _lease_heartbeat(
    repo: ClipJobRepository,
    *,
    job_id: str,
    claim_token: str,
    stop: asyncio.Event,
) -> None:
    """Extend lease while analysis runs so reclaim cannot steal a live worker."""
    renew = getattr(repo, "renew_lease", None)
    if not callable(renew):
        return
    lease_seconds = max(1, int(get_settings().arq_job_timeout))
    interval = max(15, lease_seconds // 3)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            ok = renew(job_id, claim_token=claim_token, lease_seconds=lease_seconds)
            if not ok:
                logger.warning(
                    "event=clip_job_lease_renew_failed job_id=%s",
                    job_id,
                )
                return


async def finalize_completed_clip_job(
    *,
    job: Any,
    repo: ClipJobRepository,
    result: dict[str, Any],
    job_id: str,
    effective_user_id: str,
    tricks_list: list[str],
    label: str,
    meta: dict[str, Any],
    file_path: str,
    storage_key: str,
    engine: Any,
    t_job_start: float,
    degraded: bool = False,
    claim_token: str | None = None,
) -> None:
    """
    Shared post-analysis path: playback hints, stats/recap, persist completed job,
    optional retention, upload cleanup. Used for full Gemini success and degraded completion.
    """
    settings = get_settings()
    skip_remote_storage_delete = merge_playback_hints_into_result(
        result,
        clip_metadata=meta,
        storage_key=storage_key or "",
        settings=settings,
    )
    _maybe_attach_attempt_compare(
        result,
        user_id=effective_user_id,
        job_id=job_id,
        tricks_raw=tricks_list,
    )
    _record_trick_stat(
        job_id=job_id,
        user_id=effective_user_id,
        clip_label=label,
        clip_metadata=meta,
        result=result,
    )
    _maybe_attach_session_recap(
        result,
        user_id=effective_user_id,
        job_id=job_id,
        tricks_raw=tricks_list,
    )
    token = claim_token or getattr(job, "claim_token", None)
    job.with_status("completed", result_json=result)

    readiness = str(result.get("review_readiness") or "")
    if readiness in CHARGEABLE_READINESS:
        persisted = _persist_claimed(repo, job, claim_token=token)
    else:
        persisted = _release_quota_and_persist(
            repo,
            job,
            claim_token=token,
            reason="provider_degraded" if degraded else "review_insufficient",
        )
    if not persisted:
        await _cleanup_upload(
            file_path, storage_key, skip_remote_delete=skip_remote_storage_delete
        )
        return
    _sync_v1_clip_terminal(job_id, failed=False, result=result)

    elapsed_ms = int((time.perf_counter() - t_job_start) * 1000)
    log_beta(
        "beta_job_completed",
        job_id=job_id,
        readiness=str(result.get("review_readiness") or ""),
        elapsed_ms=elapsed_ms,
        degraded=degraded,
    )
    logger.info(
        "event=clip_job_completed readiness=%s elapsed_ms=%s degraded=%s",
        result.get("review_readiness"),
        elapsed_ms,
        degraded,
    )

    try:
        from app.models import UserModel

        if effective_user_id:
            with Session(engine) as _s:
                _u = _s.get(UserModel, effective_user_id)
                _consented = bool(_u and _u.clip_retention_consent)
            if _consented:
                retain_clip(
                    file_path=file_path,
                    job_id=job_id,
                    user_id=effective_user_id,
                    clip_label=label,
                    clip_metadata=meta,
                    result=result,
                    retention_dir=settings.retention_dir,
                )
    except Exception:
        logger.warning(
            "clip retention check failed for job_id=%s",
            job_id,
            exc_info=True,
        )

    await _cleanup_upload(
        file_path, storage_key, skip_remote_delete=skip_remote_storage_delete
    )


def _technical_quality_summary(first: dict[str, Any]) -> str:
    parts: list[str] = []
    r = first.get("review_readiness")
    if r:
        parts.append(f"readiness={r}")
    if first.get("motion_detected") is False:
        parts.append("low motion across sampled frames")
    mb = first.get("mean_brightness_0_1")
    if isinstance(mb, (int, float)) and mb < 0.11:
        parts.append("low brightness in samples")
    lv = first.get("laplacian_var_mean")
    if isinstance(lv, (int, float)):
        parts.append(f"sharpness_metric_mean={lv:.1f} (Laplacian variance on scaled frames)")
    ds = first.get("duration_seconds")
    if isinstance(ds, (int, float)) and ds < 0.9:
        parts.append("short duration in samples")
    return "; ".join(parts) if parts else "no extra limits flagged in automated pass"


async def run_clip_job(
    job_id: str,
    file_path: str,
    repo: ClipJobRepository,
    *,
    user_id: str = "",
    storage_key: str = "",
) -> None:
    structlog.contextvars.bind_contextvars(job_id=job_id)
    from app.core.database import get_engine
    engine = get_engine()
    t_job = time.perf_counter()
    claim_token: str | None = None
    lease_stop: asyncio.Event | None = None
    lease_task: asyncio.Task[None] | None = None
    try:
        # CAS claim pending → processing so concurrent ARQ deliveries do not
        # both run Gemini. Terminal / lost-claim returns None (skip).
        claim = getattr(repo, "try_claim_for_processing", None)
        if callable(claim):
            job = claim(job_id)
        else:
            job = repo.get(job_id)
            if job is not None and job.status not in ("completed", "failed"):
                from app.core.config import get_settings as _gs

                job.take_lease(lease_seconds=max(1, int(_gs().arq_job_timeout)))
                repo.update(job)

        if job is None:
            existing = repo.get(job_id)
            if existing is None:
                logger.warning("event=clip_job_failed reason=missing_record")
            else:
                logger.info(
                    "event=clip_job_skipped reason=unclaimed_or_terminal status=%s",
                    existing.status,
                )
            return

        claim_token = getattr(job, "claim_token", None)
        if claim_token:
            lease_stop = asyncio.Event()
            lease_task = asyncio.create_task(
                _lease_heartbeat(
                    repo,
                    job_id=job_id,
                    claim_token=claim_token,
                    stop=lease_stop,
                )
            )

        logger.info(
            "event=clip_job_started path_tail=%s",
            os.path.basename(file_path),
        )
        log_beta("beta_job_started", job_id=job_id)

        await asyncio.sleep(0.02)

        meta: dict[str, Any] = (
            job.clip_metadata if isinstance(job.clip_metadata, dict) else {}
        )
        label = job.clip_label.strip() or "untagged"
        tricks_raw = meta.get("tricks", [])
        tricks_list = (
            [t for t in tricks_raw if isinstance(t, str)]
            if isinstance(tricks_raw, list)
            else []
        )

        try:
            # Reject missing/empty files and uploads whose header isn't a known video
            # container (magic-byte sniff) before spinning up OpenCV/Gemini.
            if (
                not os.path.isfile(file_path)
                or os.path.getsize(file_path) == 0
                or not looks_like_video(file_path)
            ):
                job.with_status("failed", failure_reason=FAILURE_VIDEO_UNREADABLE)
                if _release_quota_and_persist(
                    repo,
                    job,
                    claim_token=claim_token,
                    reason=FAILURE_VIDEO_UNREADABLE,
                ):
                    _sync_v1_clip_terminal(job_id, failed=True)
                log_beta(
                    "beta_job_failed",
                    job_id=job_id,
                    failure_reason=FAILURE_VIDEO_UNREADABLE,
                )
                logger.info(
                    "event=clip_job_failed failure_reason=%s",
                    FAILURE_VIDEO_UNREADABLE,
                )
                await _cleanup_upload(file_path, storage_key)
                return

            first = analyze_video_first_pass(file_path)
            logger.info(
                "event=clip_job_file_validated video_readable=%s",
                first.get("video_readable"),
            )

            if not first.get("video_readable"):
                job.with_status("failed", failure_reason=FAILURE_VIDEO_UNREADABLE)
                if _release_quota_and_persist(
                    repo,
                    job,
                    claim_token=claim_token,
                    reason=FAILURE_VIDEO_UNREADABLE,
                ):
                    _sync_v1_clip_terminal(job_id, failed=True)
                log_beta(
                    "beta_job_failed",
                    job_id=job_id,
                    failure_reason=FAILURE_VIDEO_UNREADABLE,
                )
                logger.info(
                    "event=clip_job_failed failure_reason=%s",
                    FAILURE_VIDEO_UNREADABLE,
                )
                await _cleanup_upload(file_path, storage_key)
                return

            cam = ClipAnalysisMetadata.from_job_upload(
                video_path=file_path,
                clip_label=label,
                stance=str(meta.get("stance") or ""),
                obstacle=str(meta.get("obstacle") or ""),
                tricks=tricks_list,
                duration_seconds=first.get("duration_seconds"),
                mime_type=guess_clip_mime(file_path),
                first_pass_readiness=str(first.get("review_readiness") or "usable"),
                technical_quality_summary=_technical_quality_summary(first),
            )

            settings = get_settings()
            tier_norm = normalize_tier(job.tier)
            analysis_provider = resolve_analysis_provider_for_tier(tier_norm, settings)
            review_model = normalized_review_model_for_provider(analysis_provider)
            pegasus_model = (settings.twelvelabs_model or "pegasus1.5").strip()
            main_model = (
                resolve_gemini_model_for_tier(tier_norm, settings)
                if analysis_provider == "gemini"
                else pegasus_model
            )

            # Tier-aware prompt for Gemini; Pegasus builds its own prompt in the analyzer.
            pack = build_tier_aware_prompt(cam, tier_norm)

            content_sha256 = str(meta.get("content_sha256") or "")
            tl_asset_id = ""
            cached_analysis: GeminiClipAnalysis | None = None
            if analysis_provider == "gemini":
                cached_analysis = await _gemini_cache_get(content_sha256, tier_norm)

            t_main = time.time()
            if cached_analysis is not None:
                gemini = cached_analysis
                logger.info(
                    "gemini_cache_hit",
                    job_id=job_id,
                    tier=tier_norm,
                    sha=content_sha256[:8],
                )
            elif analysis_provider == "gemini":
                try:
                    gemini = await analyze_clip_with_gemini(
                        file_path,
                        cam,
                        job_id=job_id,
                        prompt_pack_override=pack,
                        settings=settings,
                        account_tier=tier_norm,
                    )
                except GeminiPipelineError as e:
                    result = build_degraded_provider_failure_result(
                        first,
                        label,
                        pipeline_reason=e.reason,
                        pipeline_detail=e.detail or "",
                    )
                    log_beta(
                        "beta_job_provider_degraded",
                        job_id=job_id,
                        pipeline_reason=e.reason,
                    )
                    logger.info(
                        "event=clip_job_completed_degraded pipeline_reason=%s detail=%s",
                        e.reason,
                        (e.detail or "")[:120],
                    )
                    await finalize_completed_clip_job(
                        job=job,
                        repo=repo,
                        result=result,
                        job_id=job_id,
                        effective_user_id=user_id or job.user_id,
                        tricks_list=tricks_list,
                        label=label,
                        meta=meta,
                        file_path=file_path,
                        storage_key=storage_key,
                        engine=engine,
                        t_job_start=t_job,
                        degraded=True,
                        claim_token=claim_token,
                    )
                    return

                await _gemini_cache_set(content_sha256, tier_norm, gemini)
                record_gemini_call(main_model)
            else:
                try:
                    gemini, tl_asset_id = await analyze_clip_with_twelvelabs(
                        file_path,
                        cam,
                        job_id=job_id,
                        settings=settings,
                        account_tier=tier_norm,
                    )
                except GeminiPipelineError as e:
                    result = build_degraded_provider_failure_result(
                        first,
                        label,
                        pipeline_reason=e.reason,
                        pipeline_detail=e.detail or "",
                    )
                    log_beta(
                        "beta_job_provider_degraded",
                        job_id=job_id,
                        pipeline_reason=e.reason,
                    )
                    logger.info(
                        "event=clip_job_completed_degraded pipeline_reason=%s detail=%s",
                        e.reason,
                        (e.detail or "")[:120],
                    )
                    await finalize_completed_clip_job(
                        job=job,
                        repo=repo,
                        result=result,
                        job_id=job_id,
                        effective_user_id=user_id or job.user_id,
                        tricks_list=tricks_list,
                        label=label,
                        meta=meta,
                        file_path=file_path,
                        storage_key=storage_key,
                        engine=engine,
                        t_job_start=t_job,
                        degraded=True,
                        claim_token=claim_token,
                    )
                    return

                record_gemini_call(pegasus_model)

            _main_duration_ms = round((time.time() - t_main) * 1000)
            logger.info(
                "provider_call_complete",
                job_id=job_id,
                provider=analysis_provider,
                model=main_model,
                tier=tier_norm,
                stage="analyze",
                outcome="ok",
                duration_ms=_main_duration_ms,
                cache_hit=cached_analysis is not None,
                asset_id=tl_asset_id[:12] if tl_asset_id else None,
            )
            try:
                import sentry_sdk

                sentry_sdk.set_measurement(
                    "gemini_call_duration_ms",
                    _main_duration_ms,
                    "millisecond",
                )
            except Exception:
                pass

            enrichment: dict[str, Any] | None = None
            enrichment_attempted = False
            enrichment_model: str | None = None
            if analysis_provider == "gemini" and settings.gemini_api_key:
                enrichment_model = resolve_gemini_model_for_tier(tier_norm, settings)
                if gemini_circuit.is_open:
                    logger.warning(
                        "Gemini circuit breaker is OPEN — skipping enrichment for job_id=%s",
                        job_id,
                    )
                    enrichment = None
                else:
                    enrichment_attempted = True
                    t_enrich = time.time()
                    try:
                        reviewer = GeminiReviewer(
                            settings.gemini_api_key,
                            model=enrichment_model,
                            inline_max_bytes=settings.gemini_inline_max_bytes,
                        )
                        enrichment = await reviewer.enrich(
                            file_path=file_path,
                            clip_label=label,
                            clip_metadata=meta,
                            user_id=user_id or job.user_id,
                        )
                        gemini_circuit.record_success()
                        logger.info(
                            "provider_call_complete",
                            job_id=job_id,
                            provider="gemini",
                            model=enrichment_model,
                            tier=tier_norm,
                            stage="enrich",
                            outcome="ok",
                            duration_ms=round((time.time() - t_enrich) * 1000),
                        )
                        record_gemini_call(enrichment_model)
                    except Exception:
                        logger.exception(
                            "Gemini enrichment failed after retries job_id=%s",
                            job_id,
                        )
                        gemini_circuit.record_failure()
                        enrichment = None
            elif analysis_provider == "twelvelabs" and settings.twelvelabs_api_key:
                enrichment_model = pegasus_model
                enrichment_attempted = True
                t_enrich = time.time()
                try:
                    tl_reviewer = TwelveLabsReviewer(settings)
                    enrichment = await tl_reviewer.enrich(
                        asset_id=tl_asset_id,
                        clip_label=label,
                        clip_metadata=meta,
                        user_id=user_id or job.user_id,
                    )
                    logger.info(
                        "provider_call_complete",
                        job_id=job_id,
                        provider="twelvelabs",
                        model=pegasus_model,
                        tier=tier_norm,
                        stage="enrich",
                        outcome="ok",
                        duration_ms=round((time.time() - t_enrich) * 1000),
                        asset_id=tl_asset_id[:12] if tl_asset_id else None,
                    )
                    record_gemini_call(pegasus_model)
                except Exception:
                    logger.exception(
                        "Twelve Labs enrichment failed after retries job_id=%s",
                        job_id,
                    )
                    enrichment = None

            trick_str = tricks_list[0] if tricks_list else ""
            stance_str = str(meta.get("stance") or "").strip()

            result = build_completed_result_from_gemini(
                gemini,
                first,
                label,
                gemini_enrichment=enrichment,
                enrichment_attempted=enrichment_attempted,
                trick=trick_str,
                stance=stance_str,
                enrichment_model=enrichment_model,
                review_model=review_model,
            )
            await finalize_completed_clip_job(
                job=job,
                repo=repo,
                result=result,
                job_id=job_id,
                effective_user_id=user_id or job.user_id,
                tricks_list=tricks_list,
                label=label,
                meta=meta,
                file_path=file_path,
                storage_key=storage_key,
                engine=engine,
                t_job_start=t_job,
                degraded=False,
                claim_token=claim_token,
            )
        except Exception:
            logger.exception("event=clip_job_failed reason=internal_error")
            job.with_status("failed", failure_reason="internal_error")
            if _release_quota_and_persist(
                repo, job, claim_token=claim_token, reason="internal_error"
            ):
                _sync_v1_clip_terminal(job_id, failed=True)
            log_beta("beta_job_failed", job_id=job_id, failure_reason="internal_error")
            logger.info("event=clip_job_failed failure_reason=internal_error")
            await _cleanup_upload(file_path, storage_key)
    finally:
        if lease_stop is not None:
            lease_stop.set()
        if lease_task is not None:
            try:
                await lease_task
            except Exception:
                logger.debug("lease heartbeat task ended with error", exc_info=True)
        structlog.contextvars.unbind_contextvars("job_id")


def _record_trick_stat(
    job_id: str,
    user_id: str,
    clip_label: str,
    clip_metadata: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """
    Write TrickStat rows if the skater named at least one trick.
    Does not fail the job if stats recording errors.
    """
    tricks = clip_metadata.get("tricks", [])
    if not tricks:
        return

    try:
        from sqlmodel import Session

        from app.core.database import get_engine
        from app.models import TrickStatModel
        from app.services.milestones import check_milestones

        engine = get_engine()

        landed_resolved = resolve_landed_status(result.get("landed"), None)
        landed = landed_resolved if landed_resolved in ("yes", "no") else None

        stance = clip_metadata.get("stance", "")
        obstacle = clip_metadata.get("obstacle", "")
        readiness = result.get("review_readiness", "insufficient")

        with Session(engine) as session:
            skate_sid = clip_metadata.get("v1_skate_session_id")
            if isinstance(skate_sid, str) and skate_sid.strip():
                sid = skate_sid.strip()
            else:
                sid = resolve_session_id(session, user_id)
            pk = result.get("primary_issue_key")
            pl = result.get("primary_issue_label")
            bc = result.get("best_cue")
            bd = result.get("best_drill")
            rm = str(result.get("review_method") or "first_pass_only")
            gu = bool(result.get("gemini_used"))
            tls = result.get("technical_limit_summary")
            land_score_value: float | None = None
            raw_land_score = result.get("land_score")
            if landed == "yes" and isinstance(raw_land_score, (int, float)):
                score = round(float(raw_land_score) + 1e-9, 1)
                if 0.0 <= score <= 10.0:
                    land_score_value = score
            tricks_in_clip = len(
                [t for t in tricks[:3] if isinstance(t, str) and t.strip()]
            )
            clean_tricks: list[str] = []
            for trick_name in tricks[:3]:
                if not isinstance(trick_name, str) or not trick_name.strip():
                    continue
                tn = normalize_trick_name(trick_name)
                clean_tricks.append(tn)
                stat = TrickStatModel(
                    user_id=user_id,
                    job_id=job_id,
                    trick_name=tn,
                    stance=str(stance or ""),
                    obstacle=str(obstacle or ""),
                    landed=landed,
                    review_readiness=str(readiness or "insufficient"),
                    primary_issue_key=pk if isinstance(pk, str) else None,
                    primary_issue_label=pl if isinstance(pl, str) else None,
                    best_cue=bc if isinstance(bc, str) else None,
                    best_drill=bd if isinstance(bd, str) else None,
                    review_method=rm,
                    gemini_used=gu,
                    session_id=sid,
                    technical_limit_summary=tls if isinstance(tls, str) else None,
                    land_score=land_score_value,
                )
                session.add(stat)
                session.flush()  # make row visible for milestone queries

                check_milestones(
                    session,
                    user_id=user_id,
                    job_id=job_id,
                    trick_name=tn,
                    landed=landed,
                    session_id=sid,
                    tricks_in_clip=tricks_in_clip,
                )
            record_matching_line_attempts(
                session,
                user_id=user_id,
                job_id=job_id,
                clip_tricks=clean_tricks,
                landed=landed,
                session_id=sid,
            )
            session.commit()
        logger.info("Recorded trick stats for job_id=%s tricks=%s", job_id, tricks)
    except Exception:
        logger.warning("Could not record trick stats for job_id=%s", job_id, exc_info=True)
