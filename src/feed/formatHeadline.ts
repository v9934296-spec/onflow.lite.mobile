import type {
  BattleStartedPayload,
  BattleWonPayload,
  ComparisonSurfacedPayload,
  FeedEvent,
  FirstLandPayload,
  MakeRateJumpPayload,
  SessionRecapPayload,
} from "../types/feedEvent";

const toDisplayName = (event: FeedEvent): string => event.user.tag_name || event.user.username;
const lower = (value: string): string => value.toLowerCase();

export function formatEventHeadline(event: FeedEvent): string {
  const name = toDisplayName(event);

  switch (event.event_type) {
    case "first_land": {
      const payload = event.payload as FirstLandPayload;
      return `${name} landed their first ${lower(payload.trick_display)}`;
    }
    case "make_rate_jump": {
      const payload = event.payload as MakeRateJumpPayload;
      return `${name} hit a new make rate on ${lower(payload.trick_display)}s (${payload.make_rate_before_pct}% → ${payload.make_rate_after_pct}%)`;
    }
    case "battle_started": {
      const payload = event.payload as BattleStartedPayload;
      return `${name} started battling ${lower(payload.trick_display)}`;
    }
    case "battle_won": {
      const payload = event.payload as BattleWonPayload;
      return `${name} landed ${lower(payload.trick_display)} after ${payload.total_attempts} attempts`;
    }
    case "comparison_surfaced": {
      const payload = event.payload as ComparisonSurfacedPayload;
      return `${name} posted a side-by-side: ${lower(payload.trick_display)} then vs now`;
    }
    case "session_recap": {
      const payload = event.payload as SessionRecapPayload;
      const breakthroughs = `breakthrough${payload.breakthrough_count === 1 ? "" : "s"}`;
      return `${name} wrapped a session${payload.spot_label ? ` at ${payload.spot_label}` : ""} — ${payload.attempt_count} attempts, ${payload.breakthrough_count} ${breakthroughs}`;
    }
    default:
      return `${name} made progress`;
  }
}

export function formatEventTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
