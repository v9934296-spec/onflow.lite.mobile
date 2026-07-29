"""
Clip retention pipeline — keeps consented users' clips for dataset building.

Clips are stored locally under ONFLOW_RETENTION_DIR (default: data/retained/)
with a metadata sidecar JSON containing analysis fields, trick label, stance,
landed status, and user context (no email).

Files land at:
  {retention_dir}/{user_id}/{canonical_trick}/{job_id}.mp4
  {retention_dir}/{user_id}/{canonical_trick}/{job_id}.json

PRIVACY:
  - Only runs when user has explicitly opted in (users.clip_retention_consent)
  - Consent is set via POST /api/v1/auth/clip-retention with { "consent": true }
  - Legacy: POST /api/v1/auth/clip-retention-consent (same storage)
  - Consent can be revoked at any time (POST with { "consent": false })
  - No clips are retained without explicit opt-in
  - Metadata sidecar does NOT include email, only user_id
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def user_has_clip_retention_consent(user_id: str) -> bool:
    """True if the users row has opted into clip retention."""
    uid = (user_id or "").strip()
    if not uid:
        return False
    try:
        from sqlmodel import Session

        from app.core.database import get_engine
        from app.models import UserModel

        with Session(get_engine()) as session:
            u = session.get(UserModel, uid)
            return bool(u and u.clip_retention_consent)
    except Exception:
        logger.warning(
            "user_has_clip_retention_consent: lookup failed user_id=%s",
            uid,
            exc_info=True,
        )
        return False


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def retain_clip(
    *,
    file_path: str | Path,
    job_id: str,
    user_id: str,
    clip_label: str,
    clip_metadata: dict[str, Any],
    result: dict[str, Any],
    retention_dir: str | Path,
) -> bool:
    """
    Copy a clip and its analysis metadata to the retention directory.

    Returns True if retained successfully, False on any error (non-fatal).
    The original file is NOT deleted — the worker handles cleanup after this.
    """
    src = Path(file_path)
    if not src.is_file():
        logger.warning("retain_clip: source missing %s", src)
        return False

    # Build structured path
    tricks = clip_metadata.get("tricks", [])
    trick_name = "untagged"
    if tricks and isinstance(tricks, list):
        first = tricks[0] if isinstance(tricks[0], str) else ""
        if first.strip():
            # Use the trick registry if available, otherwise clean lowercase
            try:
                from app.services.trick_registry import normalize_trick_name

                trick_name = normalize_trick_name(first)
            except ImportError:
                trick_name = first.strip().lower()
    # Sanitize for filesystem
    trick_name = trick_name.replace(" ", "_").replace("/", "_").replace("\\", "_")

    dest_dir = Path(retention_dir) / user_id / trick_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = src.suffix or ".mp4"
    clip_dest = dest_dir / f"{job_id}{ext}"
    meta_dest = dest_dir / f"{job_id}.json"

    try:
        # Copy clip (don't move — worker still needs to clean up)
        shutil.copy2(str(src), str(clip_dest))

        # Write metadata sidecar
        sidecar = {
            "job_id": job_id,
            "user_id": user_id,
            "clip_label": clip_label,
            "trick_name": trick_name,
            "stance": clip_metadata.get("stance", ""),
            "obstacle": clip_metadata.get("obstacle", ""),
            "tricks": clip_metadata.get("tricks", []),
            "landed": result.get("landed"),
            "review_readiness": result.get("review_readiness"),
            "review_summary": result.get("review_summary", ""),
            "coaching": result.get("coaching"),
            "quality_signals": result.get("quality_signals"),
            "retained_at": _iso(datetime.now(timezone.utc)),
        }
        meta_dest.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

        logger.info(
            "retain_clip: saved %s → %s",
            job_id,
            clip_dest.relative_to(Path(retention_dir)),
        )
        return True

    except Exception:
        logger.warning("retain_clip: failed for job_id=%s", job_id, exc_info=True)
        # Clean up partial writes
        for p in (clip_dest, meta_dest):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        return False
