import type { CurrentFocus } from "./components/CurrentFocusHeader";
import type { MomentumState } from "./components/MomentumChip";
import type { TrickSummary } from "./components/TrickCard";
import type { TrickStatSummary, WhatsNextPayload } from "./api/progressionApi";

const MS_PER_DAY = 24 * 60 * 60 * 1000;

export function daysSince(iso: string): number {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return Infinity;
  return Math.floor((Date.now() - t) / MS_PER_DAY);
}

export function isWithin30Days(lastAttempted: string): boolean {
  return daysSince(lastAttempted) <= 30;
}

export function formatTrickDisplay(trickName: string): string {
  return trickName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function inferBattleStatus(stat: TrickStatSummary): TrickSummary["battle_status"] {
  if (!isWithin30Days(stat.last_attempted)) return "dormant";
  if (stat.percentage >= 80) return "won";
  if (stat.attempts >= 3 && stat.percentage < 80) return "active";
  return "none";
}

export function inferMomentumState(stat: TrickStatSummary): MomentumState | null {
  if (stat.attempts < 2) return null;
  const trend = stat.trend_last_5_make_rate ?? 0;
  const heatingUp = trend > stat.percentage && stat.percentage < 80;
  if (stat.percentage >= 80) return "dialed";
  if (stat.percentage >= 60 && stat.attempts >= 5) return "consistent";
  if (heatingUp) return "heating_up";
  if (stat.attempts >= 10 && stat.percentage < 40) return "stalled";
  return null;
}

export function adaptTrickStat(stat: TrickStatSummary): TrickSummary {
  return {
    trick_id: stat.trick_name,
    display_name: formatTrickDisplay(stat.trick_name),
    make_rate_pct: Math.round(stat.percentage),
    last_clip_at: stat.last_attempted,
    battle_status: inferBattleStatus(stat),
    momentum_state: inferMomentumState(stat),
  };
}

export function adaptTrickStats(stats: TrickStatSummary[]): TrickSummary[] {
  return [...stats]
    .sort((a, b) => new Date(b.last_attempted).getTime() - new Date(a.last_attempted).getTime())
    .map(adaptTrickStat);
}

export function buildCurrentFocus(
  whatsNext: WhatsNextPayload | null,
  stats: TrickStatSummary[],
): CurrentFocus {
  if (stats.length === 0) {
    return {
      trick_id: null,
      display_name: null,
      battle_duration_days: null,
      last_session_summary: null,
      momentum_state: null,
      empty_state: "no_clips",
    };
  }

  const focusName =
    whatsNext?.has_recommendation && whatsNext.focus_trick?.trim()
      ? whatsNext.focus_trick.trim().toLowerCase()
      : [...stats].sort(
          (a, b) => new Date(b.last_attempted).getTime() - new Date(a.last_attempted).getTime(),
        )[0]?.trick_name ?? null;

  if (!focusName) {
    return {
      trick_id: null,
      display_name: null,
      battle_duration_days: null,
      last_session_summary: null,
      momentum_state: null,
      empty_state: "no_active_battle",
    };
  }

  const focusStat = stats.find((s) => s.trick_name === focusName);
  const message = whatsNext?.message?.trim();

  return {
    trick_id: focusName,
    display_name: formatTrickDisplay(focusName),
    battle_duration_days: focusStat ? Math.max(1, daysSince(focusStat.last_attempted) || 1) : null,
    last_session_summary:
      message && whatsNext?.has_recommendation
        ? { delta_summary: message, delta_type: "session_completed" }
        : null,
    momentum_state: focusStat ? inferMomentumState(focusStat) : null,
  };
}

export function pickActiveBattle(tricks: TrickSummary[]): TrickSummary | null {
  return tricks.find((t) => t.battle_status === "active") ?? null;
}
