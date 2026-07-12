export type AnalyticsEvent =
  | "home_viewed"
  | "clip_film_started"
  | "trick_selected"
  | "session_attempt_logged"
  | "session_ended"
  | "session_recap_viewed"
  | "session_history_viewed"
  | "session_history_opened"
  | "feed_viewed"
  | "paywall_viewed"
  | "notifications_viewed"
  | "capture_completed"
  | "capture_failed"
  | "capture_interrupted"
  | "land_reported"
  | "log_viewed"
  | "log_exported"
  | "log_cleared"
  | "storage_error";

export function track(event: AnalyticsEvent, props?: Record<string, string | number | boolean>): void {
  if (__DEV__) {
    console.log("[analytics]", event, props ?? {});
  }
}
