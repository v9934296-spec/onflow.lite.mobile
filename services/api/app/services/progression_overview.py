"""P.T.E. Tech 1.0 — Progression overview aggregation from TrickStat rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.models import TrickStatModel


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat().replace("+00:00", "Z")


def _utc_date(dt: datetime) -> date:
    """Calendar day in UTC (matches streak / 'today' semantics)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).date()
    return dt.astimezone(timezone.utc).date()


def _best_land_score_for_trick(rows: list[TrickStatModel]) -> float | None:
    scores = [r.land_score for r in rows if r.landed == "yes" and r.land_score is not None]
    if not scores:
        return None
    return round(max(float(s) for s in scores), 1)


def _best_land_job_id_for_trick(rows: list[TrickStatModel]) -> str | None:
    scored = [
        (float(r.land_score), r.created_at, r.job_id)
        for r in rows
        if r.landed == "yes" and r.land_score is not None
    ]
    if not scored:
        return None
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return scored[0][2]


def build_progression_overview(rows: list[TrickStatModel]) -> dict[str, Any]:
    """
    Build the full progression overview payload from ALL of a user's trick_stats rows.

    Returns a dict with:
    - total_sessions (int): count of distinct session_id values
    - total_attempts (int): total trick_stats rows
    - total_makes (int): rows where landed == "yes"
    - global_make_rate (float): percentage 0.0–100.0, rounded to 1 decimal
    - total_tricks_attempted (int): count of distinct trick_name values
    - top_5_tricks (list[dict]): top 5 tricks by attempt count, each with:
        - trick_name (str)
        - attempts (int)
        - makes (int)
        - percentage (float)
        - last_attempted (str ISO)
        - dominant_issue_key (str | None)
        - dominant_issue_label (str | None)
    - recent_activity (list[dict]): last 10 attempts, newest first, each with:
        - trick_name (str)
        - landed (str | None)
        - created_at (str ISO)
        - job_id (str)
        - session_id (str | None)
    - current_streak (int): consecutive calendar days (UTC) with at least one
      trick_stats row, counting backward from today. 0 if no clips today.
    - longest_streak (int): longest-ever consecutive-day run.
    - sessions_this_week (int): distinct session_ids in last 7 calendar days.
    - most_recent_session_id (str | None): the session_id of the newest row.
    """
    if not rows:
        return _empty_overview()

    # --- basic counts ---
    total = len(rows)
    makes = sum(1 for r in rows if r.landed == "yes")
    session_ids = {r.session_id for r in rows if r.session_id}
    trick_names = {r.trick_name for r in rows}

    # --- top 5 tricks ---
    by_trick: dict[str, list[TrickStatModel]] = defaultdict(list)
    for r in rows:
        by_trick[r.trick_name].append(r)

    top5 = []
    for name, trows in sorted(by_trick.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
        t_makes = sum(1 for r in trows if r.landed == "yes")
        t_total = len(trows)
        newest = max(trows, key=lambda r: r.created_at)
        issue_keys = [r.primary_issue_key for r in trows if r.primary_issue_key]
        dom = Counter(issue_keys).most_common(1)
        dom_key = dom[0][0] if dom else None
        labels = {r.primary_issue_key: r.primary_issue_label for r in trows if r.primary_issue_key}
        top5.append(
            {
                "trick_name": name,
                "attempts": t_total,
                "makes": t_makes,
                "percentage": round((t_makes / t_total * 100) if t_total else 0, 1),
                "last_attempted": _iso(newest.created_at),
                "dominant_issue_key": dom_key,
                "dominant_issue_label": labels.get(dom_key),
                "best_land_score": _best_land_score_for_trick(trows),
                "best_land_job_id": _best_land_job_id_for_trick(trows),
            }
        )

    # --- recent activity (last 10) ---
    sorted_rows = sorted(rows, key=lambda r: r.created_at, reverse=True)
    recent = [
        {
            "trick_name": r.trick_name,
            "landed": r.landed,
            "created_at": _iso(r.created_at),
            "job_id": r.job_id,
            "session_id": r.session_id,
        }
        for r in sorted_rows[:10]
    ]

    # --- streak calculation ---
    dates = sorted({_utc_date(r.created_at) for r in rows})
    today = datetime.now(timezone.utc).date()
    current_streak = _calc_streak_from_today(dates, today)
    longest_streak = _calc_longest_streak(dates)

    # --- sessions this week ---
    week_ago = today - timedelta(days=7)
    sessions_this_week = len(
        {
            r.session_id
            for r in rows
            if r.session_id and _utc_date(r.created_at) >= week_ago
        }
    )

    most_recent = sorted_rows[0] if sorted_rows else None

    return {
        "total_sessions": len(session_ids),
        "total_attempts": total,
        "total_makes": makes,
        "global_make_rate": round((makes / total * 100) if total else 0, 1),
        "total_tricks_attempted": len(trick_names),
        "top_5_tricks": top5,
        "recent_activity": recent,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "sessions_this_week": sessions_this_week,
        "most_recent_session_id": most_recent.session_id if most_recent else None,
    }


def _calc_streak_from_today(dates: list[date], today: date) -> int:
    """Count consecutive days backward from today."""
    if not dates or dates[-1] != today:
        return 0
    streak = 1
    for i in range(len(dates) - 2, -1, -1):
        if (dates[i + 1] - dates[i]).days == 1:
            streak += 1
        else:
            break
    return streak


def _calc_longest_streak(dates: list[date]) -> int:
    """Find the longest consecutive-day run."""
    if not dates:
        return 0
    longest = 1
    current = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _empty_overview() -> dict[str, Any]:
    return {
        "total_sessions": 0,
        "total_attempts": 0,
        "total_makes": 0,
        "global_make_rate": 0.0,
        "total_tricks_attempted": 0,
        "top_5_tricks": [],
        "recent_activity": [],
        "current_streak": 0,
        "longest_streak": 0,
        "sessions_this_week": 0,
        "most_recent_session_id": None,
    }
