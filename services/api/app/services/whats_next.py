"""P.T.E. Tech 1.0 — "What's Next" engine. Surfaces ONE focus area from recent Gemini feedback."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.models import TrickStatModel


def build_whats_next(rows: list[TrickStatModel]) -> dict[str, Any]:
    """
    Analyze the user's recent trick_stats to determine their single focus area.

    Algorithm:
    1. Find the most-attempted trick across the last 3 distinct sessions.
    2. Filter rows for that trick within those sessions.
    3. Find the dominant primary_issue_key among those rows.
    4. Return the issue + its most recent drill + cue + context.

    Returns:
    - has_recommendation (bool): False if not enough data
    - focus_trick (str | None): the trick to focus on
    - focus_issue_key (str | None): the dominant coaching issue
    - focus_issue_label (str | None): human-readable label
    - focus_drill (str | None): the recommended drill from Gemini
    - focus_cue (str | None): the most recent coaching cue for this issue
    - issue_frequency (int): how many times this issue appeared in the window
    - window_attempts (int): total attempts in the analysis window
    - window_sessions (int): how many sessions were analyzed
    - confidence (str): "strong" (3+ occurrences), "moderate" (2), "emerging" (1)
    - message (str): human-readable coaching message
    """
    if not rows:
        return _empty_whats_next()

    # Sort newest first
    sorted_rows = sorted(rows, key=lambda r: r.created_at, reverse=True)

    # Get last 3 distinct session_ids
    seen_sessions: list[str] = []
    for r in sorted_rows:
        if r.session_id and r.session_id not in seen_sessions:
            seen_sessions.append(r.session_id)
        if len(seen_sessions) >= 3:
            break

    if not seen_sessions:
        return _empty_whats_next()

    # Filter to rows in those sessions
    session_set = set(seen_sessions)
    window_rows = [r for r in sorted_rows if r.session_id in session_set]

    if not window_rows:
        return _empty_whats_next()

    # Find most-attempted trick in window
    by_trick = Counter(r.trick_name for r in window_rows)
    focus_trick = by_trick.most_common(1)[0][0]

    # Filter to just that trick
    trick_rows = [r for r in window_rows if r.trick_name == focus_trick]

    # Find dominant issue
    issue_keys = [r.primary_issue_key for r in trick_rows if r.primary_issue_key]
    if not issue_keys:
        return {
            "has_recommendation": True,
            "focus_trick": focus_trick,
            "focus_issue_key": None,
            "focus_issue_label": None,
            "focus_drill": None,
            "focus_cue": None,
            "issue_frequency": 0,
            "window_attempts": len(trick_rows),
            "window_sessions": len(seen_sessions),
            "confidence": "emerging",
            "message": (
                f"You've been working on {focus_trick} — keep uploading clips "
                f"so P.T.E. Tech can identify your main focus area."
            ),
        }

    issue_counter = Counter(issue_keys)
    dom_key, dom_count = issue_counter.most_common(1)[0]

    # Get label, drill, and cue from most recent row with this issue
    dom_label: str | None = None
    dom_drill: str | None = None
    dom_cue: str | None = None
    for r in trick_rows:  # already newest-first
        if r.primary_issue_key == dom_key:
            if not dom_label and r.primary_issue_label:
                dom_label = r.primary_issue_label
            if not dom_drill and r.best_drill:
                dom_drill = r.best_drill
            if not dom_cue and r.best_cue:
                dom_cue = r.best_cue
            if dom_label and dom_drill and dom_cue:
                break

    # Confidence level
    if dom_count >= 3:
        confidence = "strong"
    elif dom_count >= 2:
        confidence = "moderate"
    else:
        confidence = "emerging"

    # Build human-readable message
    message = _build_message(
        focus_trick, dom_label or dom_key, dom_drill, confidence, dom_count
    )

    return {
        "has_recommendation": True,
        "focus_trick": focus_trick,
        "focus_issue_key": dom_key,
        "focus_issue_label": dom_label,
        "focus_drill": dom_drill,
        "focus_cue": dom_cue,
        "issue_frequency": dom_count,
        "window_attempts": len(trick_rows),
        "window_sessions": len(seen_sessions),
        "confidence": confidence,
        "message": message,
    }


def _build_message(
    trick: str,
    issue: str,
    drill: str | None,
    confidence: str,
    count: int,
) -> str:
    """Build a skater-friendly coaching message."""
    issue_lower = issue.lower() if issue else "technique"

    if confidence == "strong":
        msg = (
            f"Your {trick} has a clear pattern — {issue_lower} has come up "
            f"in {count} of your recent attempts. This is your unlock right now."
        )
    elif confidence == "moderate":
        msg = (
            f"Gemini flagged {issue_lower} on your {trick} twice recently. "
            f"Worth focusing on next session."
        )
    else:
        msg = (
            f"Early signal on your {trick} — {issue_lower} showed up in your "
            f"latest clips. Keep filming to confirm the pattern."
        )

    if drill:
        msg += f" Drill: {drill}"

    return msg


def _empty_whats_next() -> dict[str, Any]:
    return {
        "has_recommendation": False,
        "focus_trick": None,
        "focus_issue_key": None,
        "focus_issue_label": None,
        "focus_drill": None,
        "focus_cue": None,
        "issue_frequency": 0,
        "window_attempts": 0,
        "window_sessions": 0,
        "confidence": "none",
        "message": "Upload some clips so P.T.E. Tech can start tracking your progression.",
    }
