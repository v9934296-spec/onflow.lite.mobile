import type { SkateSession } from "../types/api/session";
import type { SessionAttempt } from "../types/sessionAttempt";
import type { SessionRecap, SessionRecapTrickRow } from "../types/sessionRecap";

function durationSeconds(startedAt: string, endedAt: string): number | null {
  const start = new Date(startedAt).getTime();
  const end = new Date(endedAt).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
  return Math.round((end - start) / 1000);
}

function buildTrickBreakdown(attempts: SessionAttempt[]): SessionRecapTrickRow[] {
  const byTrick = new Map<string, SessionRecapTrickRow>();
  for (const attempt of attempts) {
    const key = attempt.canonicalName;
    const row = byTrick.get(key) ?? {
      canonicalName: key,
      landed: 0,
      missed: 0,
      total: 0,
    };
    if (attempt.outcome === "landed") row.landed += 1;
    else row.missed += 1;
    row.total += 1;
    byTrick.set(key, row);
  }
  return [...byTrick.values()].sort((a, b) => b.total - a.total || a.canonicalName.localeCompare(b.canonicalName));
}

export function buildSessionRecap(
  session: SkateSession,
  attempts: SessionAttempt[],
  endedAt: string,
): SessionRecap {
  const sessionAttempts = attempts.filter((a) => a.sessionId === session.id);
  let landed = 0;
  let missed = 0;
  for (const attempt of sessionAttempts) {
    if (attempt.outcome === "landed") landed += 1;
    else missed += 1;
  }
  const total = sessionAttempts.length;

  return {
    session_id: session.id,
    started_at: session.started_at,
    ended_at: endedAt,
    spot_label: session.spot_label,
    focus_trick: session.focus_trick,
    attempts_count: total,
    landed_count: landed,
    missed_count: missed,
    landed_rate: total > 0 ? Math.round((landed / total) * 100) / 100 : null,
    duration_seconds: durationSeconds(session.started_at, endedAt),
    trick_breakdown: buildTrickBreakdown(sessionAttempts),
  };
}
