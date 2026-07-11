export type AnalyticsEvent =
  | "home_viewed"
  | "clip_film_started"
  | "trick_selected"
  | "capture_completed"
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
