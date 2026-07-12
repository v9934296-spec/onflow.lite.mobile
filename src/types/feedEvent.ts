export type ReactionType = "fire" | "saw_it" | "same_battle" | "progression";

export interface ReactionBucket {
  count: number;
  viewer_reacted: boolean;
  reactor_user_ids: string[];
}

export interface ReactionsSummary {
  fire: ReactionBucket;
  saw_it: ReactionBucket;
  same_battle: ReactionBucket;
  progression: ReactionBucket;
}

export type FeedEventType =
  | "first_land"
  | "make_rate_jump"
  | "battle_started"
  | "battle_won"
  | "comparison_surfaced"
  | "session_recap";

export interface FirstLandPayload {
  trick_id: string;
  trick_display: string;
  clip_id: string;
  clip_thumbnail_url: string;
  attempt_count_prior: number;
  pte_rating: number;
}

export interface MakeRateJumpPayload {
  trick_id: string;
  trick_display: string;
  clip_id: string;
  clip_thumbnail_url: string;
  make_rate_before_pct: number;
  make_rate_after_pct: number;
  window_session_count: number;
}

export interface BattleStartedPayload {
  trick_id: string;
  trick_display: string;
  battle_id: string;
  clip_id: string | null;
  clip_thumbnail_url: string | null;
  source: "user_declared" | "pte_inferred";
}

export interface BattleWonPayload {
  trick_id: string;
  trick_display: string;
  battle_id: string;
  first_land_clip_id: string;
  first_land_clip_thumbnail_url: string;
  total_attempts: number;
  battle_duration_days: number;
  first_attempt_clip_id: string | null;
}

export interface ComparisonSurfacedPayload {
  trick_id: string;
  trick_display: string;
  comparison_id: string;
  clip_a_id: string;
  clip_b_id: string;
  clip_a_date: string;
  clip_b_date: string;
  composite_url: string | null;
}

export interface SessionRecapPayload {
  session_id: string;
  spot_label: string | null;
  clip_count: number;
  attempt_count: number;
  tricks_attempted: string[];
  breakthrough_note: string | null;
  breakthrough_count: number;
  focus_trick?: string | null;
  completed_at?: string | null;
}

export type FeedEventPayload =
  | FirstLandPayload
  | MakeRateJumpPayload
  | BattleStartedPayload
  | BattleWonPayload
  | ComparisonSurfacedPayload
  | SessionRecapPayload;

export interface FeedEvent {
  id: string;
  user: {
    user_id: string;
    username: string;
    tag_name: string;
    profile_photo_url: string | null;
    tier: "flow" | "flow_plus" | "pro";
  };
  event_type: FeedEventType;
  event_version: string;
  payload: FeedEventPayload;
  generated_at: string;
  reactions_summary: ReactionsSummary;
}
