import { getAuthTokenProvider } from "./api/auth";
import { getApiBaseUrl } from "./api/baseUrl";
import { isExpoApiUrlConfigured } from "./api/config";
import { mergeApiTelemetryHeaders } from "./api/telemetry";

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
  | "land_reported"
  | "log_viewed"
  | "log_exported"
  | "log_cleared"
  | "storage_error"
  | "account_export_requested"
  | "account_delete_requested";

/** Best-effort in-memory buffer when offline / unauthenticated. */
const MAX_BUFFER = 40;
const buffer: Array<{ kind: AnalyticsEvent; props?: Record<string, string | number | boolean> }> =
  [];

function propsToPayload(props?: Record<string, string | number | boolean>): {
  job_id?: string;
  share_target?: string;
  error_detail?: string;
  ref_source?: string;
} {
  if (!props) return {};
  const job_id = props.job_id != null ? String(props.job_id).slice(0, 80) : undefined;
  const share_target =
    props.share_target != null ? String(props.share_target).slice(0, 32) : undefined;
  const error_detail =
    props.error != null
      ? String(props.error).slice(0, 2000)
      : props.message != null
        ? String(props.message).slice(0, 2000)
        : undefined;
  const ref_source =
    props.ref_source != null
      ? String(props.ref_source).slice(0, 32)
      : props.source != null
        ? String(props.source).slice(0, 32)
        : undefined;
  return { job_id, share_target, error_detail, ref_source };
}

async function postEvent(
  kind: AnalyticsEvent,
  props?: Record<string, string | number | boolean>,
): Promise<boolean> {
  if (!isExpoApiUrlConfigured()) return false;
  const provider = getAuthTokenProvider();
  if (!provider) return false;
  let token: string | null = null;
  try {
    token = await provider();
  } catch {
    return false;
  }
  if (!token) return false;

  const base = getApiBaseUrl().replace(/\/$/, "");
  const url = `${base}/api/v1/beta/client-events`;
  const body = { kind, ...propsToPayload(props) };
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...mergeApiTelemetryHeaders({}),
      },
      body: JSON.stringify(body),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function flushBuffer(): Promise<void> {
  if (buffer.length === 0) return;
  const pending = buffer.splice(0, buffer.length);
  for (const item of pending) {
    const ok = await postEvent(item.kind, item.props);
    if (!ok) {
      // Re-queue remaining on first failure (drop if still over cap).
      buffer.unshift(...pending.slice(pending.indexOf(item)));
      while (buffer.length > MAX_BUFFER) buffer.shift();
      return;
    }
  }
}

/**
 * Product analytics. In production, events are sent to the OnFlow API
 * (``POST /api/v1/beta/client-events``) when the user is signed in.
 * Always logs in __DEV__. Never throws.
 */
export function track(
  event: AnalyticsEvent,
  props?: Record<string, string | number | boolean>,
): void {
  if (typeof __DEV__ !== "undefined" && __DEV__) {
    console.log("[analytics]", event, props ?? {});
  }

  void (async () => {
    try {
      const ok = await postEvent(event, props);
      if (!ok) {
        buffer.push({ kind: event, props });
        while (buffer.length > MAX_BUFFER) buffer.shift();
        return;
      }
      await flushBuffer();
    } catch {
      // swallow — analytics must never break UX
    }
  })();
}
