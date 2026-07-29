"""
Structured beta funnel logging (no vendor analytics). Use for debugging and friction analysis.

Failure / client-event taxonomy (see docs/BETA_OBSERVABILITY.md):
  Auth:     invalid_session, sign_in_failed
  Upload:   upload_rejected, upload_store_failed, job_created
  Job:      job_started, job_completed, job_failed, job_resumed
  Gemini:   gemini_*, gemini_usefulness_rejected
  Quality:  clip_quality_insufficient, video_unreadable, upload_missing
  Feedback: feedback_saved, feedback_failed
  Client:   result_viewed, (optional others via POST /api/v1/beta/client-events)
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("onflow.beta")


def log_beta(name: str, **fields: Any) -> None:
    """Single-line JSON for grep-friendly logs (Railway, etc.)."""
    payload: dict[str, Any] = {"beta_event": name}
    for k, v in fields.items():
        if v is None:
            continue
        payload[k] = v
    logger.info("%s", json.dumps(payload, default=str, separators=(",", ":")))
