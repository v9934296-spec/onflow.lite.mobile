"""Deterministic compare + session summaries from TrickStat rows (no trick detection)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models import TrickStatModel
from app.services.landing_status import resolve_landed_status

READINESS_RANK = {"usable": 3, "limited": 2, "insufficient": 1}

# Result payload: latest attempt vs up to 3 prior attempts (same user + trick only).
MAX_PRIOR_FOR_COMPARE = 3


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat().replace("+00:00", "Z")


def attempt_to_dict(r: TrickStatModel) -> dict[str, Any]:
    return {
        "job_id": r.job_id,
        "landed": r.landed,
        "stance": r.stance,
        "obstacle": r.obstacle,
        "review_readiness": r.review_readiness,
        "created_at": _iso(r.created_at),
        "primary_issue_key": r.primary_issue_key,
        "primary_issue_label": r.primary_issue_label,
        "best_cue": r.best_cue,
        "best_drill": r.best_drill,
        "review_method": r.review_method,
        "gemini_used": r.gemini_used,
        "technical_limit_summary": r.technical_limit_summary,
    }


def fetch_prior_trick_stats(
    session: Session,
    user_id: str,
    trick_name_normalized: str,
    exclude_job_id: str,
    *,
    limit: int = MAX_PRIOR_FOR_COMPARE,
) -> list[TrickStatModel]:
    """Newest-first prior attempts for one trick, excluding the current job."""
    clean = trick_name_normalized.strip().lower()
    stmt = (
        select(TrickStatModel)
        .where(
            TrickStatModel.user_id == user_id,
            TrickStatModel.trick_name == clean,
            TrickStatModel.job_id != exclude_job_id,
        )
        .order_by(TrickStatModel.created_at.desc())
        .limit(limit)
    )
    return list(session.exec(stmt))


def _landed_rank(v: str | None) -> int:
    if v == "yes":
        return 3
    if v == "no":
        return 1
    return 2  # unclear / missing


def _result_landed_str(result: dict[str, Any]) -> str | None:
    return resolve_landed_status(result.get("landed"), None)


def _serialize_previous_row(r: TrickStatModel) -> dict[str, Any]:
    landed = resolve_landed_status(r.landed, None)
    return {
        "job_id": r.job_id,
        "landed": landed,
        "review_readiness": r.review_readiness,
        "primary_issue_key": r.primary_issue_key,
        "primary_issue_label": r.primary_issue_label,
        "best_cue": r.best_cue,
        "best_drill": r.best_drill,
        "created_at": _iso(r.created_at),
    }


def _dedupe_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in lines:
        t = s.strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def build_attempt_compare_block(
    *,
    trick_display_name: str,
    trick_name_normalized: str,
    job_id: str,
    latest_result: dict[str, Any],
    latest_created_at_iso: str,
    previous_rows: list[TrickStatModel],
) -> dict[str, Any] | None:
    """
    Compare current job result to up to 3 prior TrickStat rows (same user + trick).
    Returns None when there is no prior attempt (caller omits attempt_compare).
    """
    if not previous_rows:
        return None

    baseline_n = len(previous_rows)
    readiness_latest = str(latest_result.get("review_readiness") or "limited")
    r_latest = READINESS_RANK.get(readiness_latest, 0)
    landed_latest = _result_landed_str(latest_result)
    pk_latest = latest_result.get("primary_issue_key") if isinstance(latest_result.get("primary_issue_key"), str) else None
    pl_latest = latest_result.get("primary_issue_label") if isinstance(latest_result.get("primary_issue_label"), str) else None
    bc_latest = latest_result.get("best_cue") if isinstance(latest_result.get("best_cue"), str) else None
    bd_latest = latest_result.get("best_drill") if isinstance(latest_result.get("best_drill"), str) else None
    tls_latest = latest_result.get("technical_limit_summary")
    tls_latest = tls_latest if isinstance(tls_latest, str) else None

    prev_ranks = [READINESS_RANK.get(str(r.review_readiness or ""), 0) for r in previous_rows]
    avg_prev_r = sum(prev_ranks) / len(prev_ranks) if prev_ranks else 0.0
    immediate = previous_rows[0]

    improvements: list[str] = []
    repeated_issues: list[str] = []
    regressions: list[str] = []

    # Improvements (max 2)
    if r_latest > avg_prev_r + 0.49:
        improvements.append(
            "Review readiness looks stronger than your recent baseline for this trick — "
            "the clip gave the model a clearer read."
        )
    landed_prev = [r.landed for r in previous_rows]
    yes_prev = sum(1 for x in landed_prev if x == "yes")
    if landed_latest == "yes" and yes_prev < (len(previous_rows) / 2):
        improvements.append(
            "Landing reads more made than most of your last few tries for this trick name."
        )
    if len(improvements) < 2 and pk_latest:
        prev_keys = [r.primary_issue_key for r in previous_rows if r.primary_issue_key]
        if prev_keys and pk_latest not in set(prev_keys):
            improvements.append(
                "The main coaching focus shifted compared with what kept showing up on your recent tries."
            )

    improvements = _dedupe_lines(improvements)[:2]

    # Repeated issues (max 2)
    if pk_latest:
        repeat_count = sum(1 for r in previous_rows if r.primary_issue_key == pk_latest)
        if repeat_count >= 1:
            label = pl_latest or pk_latest.replace("_", " ")
            repeated_issues.append(
                f"{label} keeps showing up as the dominant focus across your recent attempts."
            )
    if len(repeated_issues) < 2 and pk_latest:
        key_counts = Counter(r.primary_issue_key for r in previous_rows if r.primary_issue_key)
        if key_counts:
            top_k, top_c = key_counts.most_common(1)[0]
            if top_c >= 2 and top_k == pk_latest:
                lab = pl_latest or str(top_k).replace("_", " ")
                line = f"Same repeat pattern ({lab}) is still central on this try."
                if line not in repeated_issues:
                    repeated_issues.append(line)
    repeated_issues = _dedupe_lines(repeated_issues)[:2]

    # Regressions (max 1)
    if r_latest < READINESS_RANK.get(str(immediate.review_readiness or ""), 0):
        regressions.append(
            "Readiness for this clip is lower than your last attempt — treat specifics as less certain."
        )
    if not regressions:
        if _landed_rank(landed_latest) < _landed_rank(immediate.landed):
            regressions.append(
                "Landing outcome looks rougher than your immediately previous attempt for this trick."
            )
    regressions = regressions[:1]

    # Summary + best next focus
    thin = baseline_n < 3
    summary_parts: list[str] = []
    if thin:
        summary_parts.append(
            f"Only {baseline_n} prior attempt(s) on record for this trick — this is a thin compare window."
        )
    summary_parts.append(
        f"This try is stacked against your {baseline_n} most recent attempt(s) for “{trick_display_name}” you logged before."
    )
    if improvements:
        summary_parts.append(" ".join(improvements[:1]))
    elif repeated_issues:
        summary_parts.append(repeated_issues[0])
    else:
        summary_parts.append(
            "Pattern is mixed: keep naming the trick the same each upload so this read stays apples-to-apples."
        )
    compare_summary = " ".join(summary_parts).strip()
    if len(compare_summary) > 720:
        compare_summary = compare_summary[:719] + "…"

    if pl_latest:
        best_next_focus = (
            f"Make your next session about one thing: {pl_latest.lower()} — adjust one mechanic at a time."
        )
    elif bc_latest:
        best_next_focus = f"Next focus: rehearse the cue you’re seeing most — {bc_latest[:180]}"
    else:
        best_next_focus = (
            "Next focus: repeat the same setup, then change one visible variable at a time "
            "(speed, pop timing, or shoulders)."
        )

    latest_attempt: dict[str, Any] = {
        "job_id": job_id,
        "landed": landed_latest,
        "review_readiness": readiness_latest,
        "primary_issue_key": pk_latest,
        "primary_issue_label": pl_latest,
        "best_cue": bc_latest,
        "best_drill": bd_latest,
        "technical_limit_summary": tls_latest,
        "created_at": latest_created_at_iso,
    }

    return {
        "compare_available": True,
        "trick_name": trick_display_name,
        "baseline_window_count": baseline_n,
        "latest_attempt": latest_attempt,
        "previous_attempts": [_serialize_previous_row(r) for r in previous_rows],
        "improvements": improvements,
        "repeated_issues": repeated_issues,
        "regressions": regressions,
        "compare_summary": compare_summary,
        "best_next_focus": best_next_focus,
    }


def build_compare_payload(rows: list[TrickStatModel], trick_name: str) -> dict[str, Any]:
    """rows: all attempts for one trick, newest first."""
    clean = trick_name.strip().lower()
    if len(rows) < 2:
        latest = rows[0] if rows else None
        return {
            "trick_name": clean,
            "compare_available": False,
            "latest_attempt": attempt_to_dict(latest) if latest else None,
            "baseline_window_count": 0,
            "repeated_issue_keys": [],
            "improving_issue_keys": [],
            "stable_strength_summary": None,
            "compare_summary": "Too little usable history for a strong compare read.",
            "trend": {
                "last_5_landed_yes": 0,
                "last_5_landed_no": 0,
                "last_5_unclear": 0,
                "last_5_usable": 0,
                "last_5_limited": 0,
                "last_5_insufficient": 0,
            },
        }

    latest = rows[0]
    # Baseline = up to 3 prior attempts (same trick, same user), newest-first in rows[1:4].
    prev_baseline = rows[1 : 1 + MAX_PRIOR_FOR_COMPARE]
    baseline_window_count = len(prev_baseline)

    def _trend(rs: list[TrickStatModel]) -> dict[str, int]:
        return {
            "last_5_landed_yes": sum(1 for x in rs if x.landed == "yes"),
            "last_5_landed_no": sum(1 for x in rs if x.landed == "no"),
            "last_5_unclear": sum(1 for x in rs if x.landed not in ("yes", "no")),
            "last_5_usable": sum(1 for x in rs if x.review_readiness == "usable"),
            "last_5_limited": sum(1 for x in rs if x.review_readiness == "limited"),
            "last_5_insufficient": sum(1 for x in rs if x.review_readiness == "insufficient"),
        }

    trend = _trend(prev_baseline)

    window4 = rows[: 1 + MAX_PRIOR_FOR_COMPARE]
    keys_ordered = [r.primary_issue_key for r in window4 if r.primary_issue_key]
    cnt = Counter(keys_ordered)
    lk = latest.primary_issue_key
    repeated_issue_keys = sorted(
        {k for k, c in cnt.items() if c >= 2 and k == lk},
    )

    old_keys = {r.primary_issue_key for r in prev_baseline if r.primary_issue_key}
    latest_key = latest.primary_issue_key
    improving_issue_keys = sorted([k for k in old_keys if k and k != latest_key])

    stable_strength_summary: str | None = None
    landed_yes_usable = sum(
        1 for r in window4 if r.landed == "yes" and r.review_readiness == "usable"
    )
    if landed_yes_usable >= 2:
        stable_strength_summary = "Consistent usable landings in recent tries for this trick."

    # compare_summary
    lines: list[str] = []
    if latest.landed == "yes" and trend["last_5_landed_no"] >= trend["last_5_landed_yes"]:
        lines.append("Landing outcome looks stronger than most recent prior attempts.")
    if repeated_issue_keys and latest_key:
        lines.append(
            f"The latest attempt still echoes a repeating focus: "
            f"{latest.primary_issue_label or latest_key}."
        )
    if improving_issue_keys:
        lines.append("Some earlier focus areas are less prominent on the latest attempt.")
    if prev_baseline and READINESS_RANK.get(latest.review_readiness, 0) > READINESS_RANK.get(
        prev_baseline[0].review_readiness, 0
    ):
        lines.append("Readiness improved versus the immediately previous attempt.")
    if not lines:
        compare_summary = (
            "Latest attempt fits your recent pattern; more clips will sharpen the compare read."
        )
    else:
        compare_summary = " ".join(lines)
        if not compare_summary.endswith("."):
            compare_summary += "."

    return {
        "trick_name": clean,
        "compare_available": True,
        "latest_attempt": attempt_to_dict(latest),
        "baseline_window_count": baseline_window_count,
        "repeated_issue_keys": repeated_issue_keys,
        "improving_issue_keys": improving_issue_keys,
        "stable_strength_summary": stable_strength_summary,
        "compare_summary": compare_summary,
        "trend": trend,
    }


def build_trick_progression(rows: list[TrickStatModel], trick_name: str) -> dict[str, Any]:
    """
    Merged trick detail + compare + coaching timeline for P.T.E. Tech dashboard.
    rows: all attempts for one trick, newest first.
    """
    clean = trick_name.strip().lower()
    if not rows:
        return {
            "trick_name": clean,
            "total_attempts": 0,
            "makes": 0,
            "percentage": 0.0,
            "attempts": [],
            "compare": build_compare_payload([], clean),
            "coaching_timeline": [],
        }

    attempts = []
    makes = 0
    for row in rows:
        attempts.append(attempt_to_dict(row))
        if row.landed == "yes":
            makes += 1

    coaching_timeline = []
    for row in rows:
        coaching_timeline.append(
            {
                "job_id": row.job_id,
                "created_at": _iso(row.created_at),
                "landed": row.landed,
                "primary_issue_key": row.primary_issue_key,
                "primary_issue_label": row.primary_issue_label,
                "best_cue": row.best_cue,
                "best_drill": row.best_drill,
                "session_id": row.session_id,
            }
        )

    return {
        "trick_name": clean,
        "total_attempts": len(attempts),
        "makes": makes,
        "percentage": round((makes / len(attempts) * 100) if attempts else 0, 1),
        "attempts": attempts,
        "compare": build_compare_payload(rows, clean),
        "coaching_timeline": coaching_timeline,
    }


def _build_coaching_recap(rows_sorted: list[TrickStatModel]) -> list[dict[str, Any]]:
    """Per-trick coaching highlight from the session's trick_stats."""
    by_trick: dict[str, list[TrickStatModel]] = defaultdict(list)
    for r in rows_sorted:
        by_trick[r.trick_name].append(r)

    recap: list[dict[str, Any]] = []
    for name, trows in by_trick.items():
        attempts = len(trows)
        makes = sum(1 for r in trows if r.landed == "yes")
        # Most recent issue and cue for this trick in this session
        issue_key: str | None = None
        issue_label: str | None = None
        cue: str | None = None
        drill: str | None = None
        for r in reversed(trows):  # newest first within session
            if not issue_key and r.primary_issue_key:
                issue_key = r.primary_issue_key
                issue_label = r.primary_issue_label
            if not cue and r.best_cue:
                cue = r.best_cue
            if not drill and r.best_drill:
                drill = r.best_drill
            if issue_key and cue and drill:
                break
        recap.append(
            {
                "trick_name": name,
                "attempts": attempts,
                "makes": makes,
                "percentage": round((makes / attempts * 100) if attempts else 0, 1),
                "issue_key": issue_key,
                "issue_label": issue_label,
                "best_cue": cue,
                "best_drill": drill,
            }
        )
    # Sort by attempts descending
    recap.sort(key=lambda x: x["attempts"], reverse=True)
    return recap


def _derive_session_focus(rows_sorted: list[TrickStatModel]) -> dict[str, Any] | None:
    """Derive a single focus recommendation from this session's data."""
    if not rows_sorted:
        return None

    # Find the most repeated issue across all tricks in this session
    issue_keys = [r.primary_issue_key for r in rows_sorted if r.primary_issue_key]
    if not issue_keys:
        return None

    counter = Counter(issue_keys)
    top_key, top_count = counter.most_common(1)[0]

    # Find the label and drill for this issue
    label: str | None = None
    drill: str | None = None
    trick: str | None = None
    for r in reversed(rows_sorted):
        if r.primary_issue_key == top_key:
            if not label and r.primary_issue_label:
                label = r.primary_issue_label
            if not drill and r.best_drill:
                drill = r.best_drill
            if not trick:
                trick = r.trick_name
            if label and drill and trick:
                break

    return {
        "issue_key": top_key,
        "issue_label": label,
        "trick_name": trick,
        "drill": drill,
        "occurrences": top_count,
    }


def build_session_payload(
    session_id: str,
    rows: list[TrickStatModel],
) -> dict[str, Any]:
    """rows: all stats rows for this session_id (any trick)."""
    if not rows:
        return {
            "session_id": session_id,
            "total_attempts": 0,
            "tricks_attempted_count": 0,
            "most_attempted_trick": None,
            "makes": 0,
            "misses": 0,
            "unclear": 0,
            "usable_clips": 0,
            "limited_clips": 0,
            "insufficient_clips": 0,
            "best_make": None,
            "weakest_pattern_key": None,
            "weakest_pattern_label": None,
            "what_improved_today": None,
            "what_to_practice_next_session": None,
            "summary": "Not enough session data yet — upload clips with named tricks to build memory.",
            "summary_confidence": "limited",
            "coaching_recap": [],
            "focus_for_next_session": None,
            "session_recap": None,
        }

    rows_sorted = sorted(rows, key=lambda r: r.created_at)
    total = len(rows_sorted)
    by_trick = Counter(r.trick_name for r in rows_sorted)
    most_attempted_trick = by_trick.most_common(1)[0][0] if by_trick else None

    makes = sum(1 for r in rows_sorted if r.landed == "yes")
    misses = sum(1 for r in rows_sorted if r.landed == "no")
    unclear = sum(1 for r in rows_sorted if r.landed not in ("yes", "no"))

    usable_clips = sum(1 for r in rows_sorted if r.review_readiness == "usable")
    limited_clips = sum(1 for r in rows_sorted if r.review_readiness == "limited")
    insufficient_clips = sum(1 for r in rows_sorted if r.review_readiness == "insufficient")

    issue_keys = [r.primary_issue_key for r in rows_sorted if r.primary_issue_key]
    wk, wc = Counter(issue_keys).most_common(1)[0] if issue_keys else (None, 0)
    label_map = {
        r.primary_issue_key: r.primary_issue_label
        for r in rows_sorted
        if r.primary_issue_key and r.primary_issue_label
    }
    weakest_pattern_label = label_map.get(wk) if wk else None

    # best_make: latest landed=yes with best readiness
    landed_rows = [r for r in reversed(rows_sorted) if r.landed == "yes"]
    best_make = None
    if landed_rows:
        best = max(
            landed_rows,
            key=lambda r: READINESS_RANK.get(r.review_readiness, 0),
        )
        best_make = {
            "trick_name": best.trick_name,
            "job_id": best.job_id,
            "created_at": _iso(best.created_at),
            "best_cue": best.best_cue,
        }

    # what_to_practice: latest best_drill for weakest pattern
    practice = None
    if wk:
        for r in reversed(rows_sorted):
            if r.primary_issue_key == wk and r.best_drill:
                practice = r.best_drill
                break

    # what_improved: compare first vs second half of session by issue repetition
    mid = total // 2
    first_half = rows_sorted[:mid] if mid else []
    second_half = rows_sorted[mid:] if mid else rows_sorted
    c1 = Counter(x.primary_issue_key for x in first_half if x.primary_issue_key)
    c2 = Counter(x.primary_issue_key for x in second_half if x.primary_issue_key)
    what_improved = None
    if first_half and second_half:
        if sum(c2.values()) < sum(c1.values()) or sum(
            1 for r in second_half if r.landed == "yes"
        ) > sum(1 for r in first_half if r.landed == "yes"):
            what_improved = (
                "Later tries in this session show fewer repeating focus issues or better landings "
                "than earlier tries."
            )

    summary_confidence: str = "usable"
    if usable_clips < 2 or (limited_clips + insufficient_clips) >= max(1, total - 1):
        summary_confidence = "limited"

    summary_parts = [
        f"This session has {total} attempt(s) across {len(by_trick)} trick name(s).",
        f"Landings recorded as makes: {makes}, misses: {misses}, unclear: {unclear}.",
    ]
    if summary_confidence == "limited":
        summary_parts.append(
            "Most clips were limited or insufficient for strong readouts — summaries stay conservative."
        )
    if wk and weakest_pattern_label:
        summary_parts.append(f"The most repeated focus area was: {weakest_pattern_label}.")

    return {
        "session_id": session_id,
        "total_attempts": total,
        "tricks_attempted_count": len(by_trick),
        "most_attempted_trick": most_attempted_trick,
        "makes": makes,
        "misses": misses,
        "unclear": unclear,
        "usable_clips": usable_clips,
        "limited_clips": limited_clips,
        "insufficient_clips": insufficient_clips,
        "best_make": best_make,
        "weakest_pattern_key": wk,
        "weakest_pattern_label": weakest_pattern_label,
        "what_improved_today": what_improved,
        "what_to_practice_next_session": practice,
        "summary": " ".join(summary_parts),
        "summary_confidence": summary_confidence,
        "coaching_recap": _build_coaching_recap(rows_sorted),
        "focus_for_next_session": _derive_session_focus(rows_sorted),
        "session_recap": build_session_recap_payload(session_id, rows_sorted),
    }


def _trick_display_name(name: str) -> str:
    t = (name or "").strip()
    if not t:
        return ""
    if t.islower() or "_" in t:
        return t.replace("_", " ").title()
    return t


def build_session_recap_payload(
    session_id: str,
    rows: list[TrickStatModel],
) -> dict[str, Any]:
    """
    Structured session recap from stored TrickStat rows (same session_id, same user in DB).
    recap_available is False when fewer than 2 attempts — embedders may omit from job JSON.
    """
    rows_sorted = sorted(rows, key=lambda r: r.created_at)
    n = len(rows_sorted)
    started = _iso(rows_sorted[0].created_at) if rows_sorted else None
    ended = _iso(rows_sorted[-1].created_at) if rows_sorted else None

    if n < 2:
        uniq_tricks = len({r.trick_name for r in rows_sorted})
        return {
            "recap_available": False,
            "session_id": session_id,
            "started_at": started,
            "ended_at": ended,
            "session_attempt_count": n,
            "trick_count": uniq_tricks,
            "trick_breakdown": [],
            "strongest_progress_area": None,
            "repeated_session_issue": None,
            "late_session_dropoff": None,
            "best_trick_of_session": None,
            "session_summary": (
                "One logged attempt is not a session pattern — add another attempt in the same visit "
                "to unlock session-level coaching."
            ),
            "next_session_focus": "Next session, log two or more attempts (same trick names) so we can compare within the session.",
            "recommended_drill": None,
        }

    by_trick: dict[str, list[TrickStatModel]] = defaultdict(list)
    for r in rows_sorted:
        by_trick[r.trick_name].append(r)

    trick_breakdown: list[dict[str, Any]] = []
    for tname, trows in sorted(by_trick.items(), key=lambda x: (-len(x[1]), x[0])):
        tsorted = sorted(trows, key=lambda r: r.created_at)
        makes = sum(1 for r in trows if r.landed == "yes")
        unclear = sum(1 for r in trows if r.landed not in ("yes", "no"))
        keys = [r.primary_issue_key for r in trows if r.primary_issue_key]
        dom_k = Counter(keys).most_common(1)[0][0] if keys else None
        lab_map = {r.primary_issue_key: r.primary_issue_label for r in trows if r.primary_issue_key}
        dom_l = lab_map.get(dom_k) if dom_k else None
        latest = tsorted[-1]
        trick_breakdown.append(
            {
                "trick_name": _trick_display_name(tname),
                "attempts": len(trows),
                "landed_count": makes,
                "unclear_count": unclear,
                "primary_repeated_issue": dom_l or (dom_k.replace("_", " ") if dom_k else None),
                "best_cue": latest.best_cue,
            }
        )

    issue_keys_all = [r.primary_issue_key for r in rows_sorted if r.primary_issue_key]
    repeated_session_issue: str | None = None
    if issue_keys_all:
        rep_k, rep_c = Counter(issue_keys_all).most_common(1)[0]
        lab_all = {
            r.primary_issue_key: r.primary_issue_label
            for r in rows_sorted
            if r.primary_issue_key and r.primary_issue_label
        }
        label = lab_all.get(rep_k) or str(rep_k).replace("_", " ")
        if rep_c >= 2:
            repeated_session_issue = (
                f"{label} kept repeating across multiple attempts this session — not a trick call, "
                "just the coaching focus that kept showing up."
            )
        else:
            repeated_session_issue = f"{label} was the most common focus label in this session."

    mid = n // 2
    first_half = rows_sorted[:mid] if mid else rows_sorted
    second_half = rows_sorted[mid:] if mid else []
    r1 = (
        sum(READINESS_RANK.get(str(r.review_readiness or ""), 0) for r in first_half) / len(first_half)
        if first_half
        else 0.0
    )
    r2 = (
        sum(READINESS_RANK.get(str(r.review_readiness or ""), 0) for r in second_half) / len(second_half)
        if second_half
        else 0.0
    )
    if second_half and r2 + 0.01 < r1:
        late_session_dropoff = (
            "Later attempts had lower review readiness than early ones — usually clip angle, "
            "lighting, or coverage limits, not assumed fatigue."
        )
    else:
        late_session_dropoff = "No obvious late-session dropoff."

    strongest_progress_area: str | None = None
    best_delta = 0.0
    best_trick_for_progress: str | None = None
    for tname, trows in by_trick.items():
        if len(trows) < 2:
            continue
        ts = sorted(trows, key=lambda r: r.created_at)
        m = max(1, len(ts) // 2)
        a, b = ts[:m], ts[m:]
        y1 = sum(1 for r in a if r.landed == "yes") / len(a) if a else 0.0
        y2 = sum(1 for r in b if r.landed == "yes") / len(b) if b else 0.0
        d = y2 - y1
        if d > best_delta + 1e-6:
            best_delta = d
            best_trick_for_progress = tname
    if best_trick_for_progress and best_delta > 0.01:
        strongest_progress_area = (
            f"{_trick_display_name(best_trick_for_progress)} showed clearer landing signals later in "
            "this session than on your first tries in the same visit."
        )
    elif second_half and r2 > r1 + 0.01:
        strongest_progress_area = (
            "Overall review readiness improved in the second half of the session versus the first attempts."
        )

    best_trick_of_session: str | None = None
    best_score: tuple[float, int, int] | None = None
    for tname, trows in by_trick.items():
        ta = len(trows)
        mk = sum(1 for r in trows if r.landed == "yes")
        rate = mk / ta if ta else 0.0
        score = (rate, mk, ta)
        if best_score is None or score > best_score:
            best_score = score
            best_trick_of_session = _trick_display_name(tname)
    if best_score and best_score[0] < 1e-6:
        best_prog: tuple[float, int, str] | None = None
        for tname, trows in by_trick.items():
            if len(trows) < 2:
                continue
            ts = sorted(trows, key=lambda r: r.created_at)
            m = max(1, len(ts) // 2)
            a, b = ts[:m], ts[m:]
            avg1 = sum(_landed_rank(r.landed) for r in a) / len(a)
            avg2 = sum(_landed_rank(r.landed) for r in b) / len(b)
            d = avg2 - avg1
            tup = (d, len(trows), tname)
            if best_prog is None or tup > best_prog:
                best_prog = tup
        if best_prog and best_prog[0] > 1e-6:
            best_trick_of_session = _trick_display_name(best_prog[2])

    focus = _derive_session_focus(rows_sorted)
    if (
        focus
        and focus.get("trick_name")
        and (focus.get("issue_label") or focus.get("issue_key"))
    ):
        tn = _trick_display_name(str(focus.get("trick_name") or ""))
        il = focus.get("issue_label") or focus.get("issue_key")
        next_session_focus = (
            f"Next session, stay on {tn or 'the same trick names'} and work one mechanic only: {il}."
        )
        recommended_drill = focus.get("drill") if isinstance(focus.get("drill"), str) else None
        if recommended_drill and len(recommended_drill) < 8:
            recommended_drill = None
    else:
        next_session_focus = (
            "Next session, keep trick names consistent and aim for 3–6 attempts in one window so "
            "session recap stays grounded in real repeats."
        )
        recommended_drill = None

    makes_all = sum(1 for r in rows_sorted if r.landed == "yes")
    misses_all = sum(1 for r in rows_sorted if r.landed == "no")
    unclear_all = sum(1 for r in rows_sorted if r.landed not in ("yes", "no"))
    summary_parts = [
        f"{n} attempts across {len(by_trick)} trick name(s) in this session.",
        f"Makes {makes_all}, misses {misses_all}, unclear {unclear_all}.",
    ]
    if n < 4:
        summary_parts.append("Small session — wording stays tight and avoids invented fatigue arcs.")
    session_summary = " ".join(summary_parts)
    if len(session_summary) > 480:
        session_summary = session_summary[:479] + "…"

    return {
        "recap_available": True,
        "session_id": session_id,
        "started_at": started,
        "ended_at": ended,
        "session_attempt_count": n,
        "trick_count": len(by_trick),
        "trick_breakdown": trick_breakdown,
        "strongest_progress_area": strongest_progress_area,
        "repeated_session_issue": repeated_session_issue,
        "late_session_dropoff": late_session_dropoff,
        "best_trick_of_session": best_trick_of_session,
        "session_summary": session_summary,
        "next_session_focus": next_session_focus,
        "recommended_drill": recommended_drill,
    }
