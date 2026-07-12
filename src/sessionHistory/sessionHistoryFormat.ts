import type { SessionRecap } from "../types/sessionRecap";

export function formatSessionHistoryDate(iso: string, now = new Date()): string {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return "Unknown date";

  const todayKey = toDateKey(now);
  const endedKey = toDateKey(date);
  if (endedKey === todayKey) return "Today";

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (endedKey === toDateKey(yesterday)) return "Yesterday";

  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function formatSessionHistoryTitle(recap: SessionRecap): string {
  if (recap.spot_label?.trim()) return recap.spot_label.trim();
  if (recap.focus_trick?.trim()) return recap.focus_trick.trim();
  if (recap.trick_breakdown[0]?.canonicalName) return recap.trick_breakdown[0].canonicalName;
  return "Session";
}

export function formatSessionHistorySubtitle(recap: SessionRecap): string {
  const date = formatSessionHistoryDate(recap.ended_at);
  if (recap.attempts_count === 0) return `${date} · No attempts logged`;
  return `${date} · ${recap.landed_count} landed · ${recap.missed_count} missed · ${recap.attempts_count} attempts`;
}

export function excludeActiveSessionFromHistory(
  recaps: SessionRecap[],
  activeSessionId: string | null,
): SessionRecap[] {
  if (!activeSessionId?.trim()) return recaps;
  return recaps.filter((r) => r.session_id !== activeSessionId);
}
