import { apiRequest } from "./client";
import type { ApiResult } from "./types";

export type ProgressionTimelineItem = {
  session_id: string;
  ended_at: string | null;
  spot: string | null;
  focus_trick: string | null;
  duration_seconds: number | null;
  clips_count: number;
  attempt_count: number;
  best_pte_score: number | null;
  thumbnail_url: string | null;
};

export type ProgressionTimelineResponse = {
  items: ProgressionTimelineItem[];
  page: number;
  page_size: number;
  has_more: boolean;
};

export type ProgressionOverview = {
  total_sessions: number;
  total_attempts: number;
  total_makes: number;
  global_make_rate: number;
  total_tricks_attempted: number;
  top_5_tricks: Array<{
    trick_name: string;
    attempts: number;
    makes: number;
    percentage: number;
  }>;
  recent_activity: Array<Record<string, unknown>>;
  current_streak: number;
  longest_streak: number;
  sessions_this_week: number;
  most_recent_session_id: string | null;
};

export type WhatsNextPayload = {
  has_recommendation: boolean;
  focus_trick: string | null;
  focus_issue_key: string | null;
  focus_issue_label: string | null;
  focus_drill: string | null;
  focus_cue: string | null;
  issue_frequency: number;
  window_attempts: number;
  window_sessions: number;
  confidence: string;
  message: string;
};

export type TrickStatSummary = {
  trick_name: string;
  attempts: number;
  makes: number;
  percentage: number;
  last_attempted: string;
  trend_last_5_make_rate?: number | null;
};

function parseItem(raw: unknown): ProgressionTimelineItem | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (typeof o.session_id !== "string") return null;
  return {
    session_id: o.session_id,
    ended_at: typeof o.ended_at === "string" ? o.ended_at : null,
    spot: typeof o.spot === "string" ? o.spot : null,
    focus_trick: typeof o.focus_trick === "string" ? o.focus_trick : null,
    duration_seconds: typeof o.duration_seconds === "number" ? o.duration_seconds : null,
    clips_count: typeof o.clips_count === "number" ? o.clips_count : 0,
    attempt_count: typeof o.attempt_count === "number" ? o.attempt_count : 0,
    best_pte_score: typeof o.best_pte_score === "number" ? o.best_pte_score : null,
    thumbnail_url: typeof o.thumbnail_url === "string" ? o.thumbnail_url : null,
  };
}

export async function fetchProgressionTimeline(
  page = 1,
  pageSize = 20,
): Promise<ApiResult<ProgressionTimelineResponse>> {
  const result = await apiRequest<unknown>(
    `/api/v1/progression/timeline?page=${page}&page_size=${pageSize}`,
    { auth: true },
  );
  if (!result.ok) return result;
  if (!result.data || typeof result.data !== "object") {
    return { ok: false, error: { kind: "malformed", message: "Could not parse progression timeline." } };
  }
  const o = result.data as Record<string, unknown>;
  const items = Array.isArray(o.items)
    ? o.items.map(parseItem).filter((item): item is ProgressionTimelineItem => Boolean(item))
    : [];
  return {
    ok: true,
    status: result.status,
    data: {
      items,
      page: typeof o.page === "number" ? o.page : page,
      page_size: typeof o.page_size === "number" ? o.page_size : pageSize,
      has_more: o.has_more === true,
    },
  };
}

export async function fetchProgressionOverview(): Promise<ApiResult<ProgressionOverview>> {
  const result = await apiRequest<unknown>("/api/v1/stats/progression/overview", { auth: true });
  if (!result.ok) return result;
  if (!result.data || typeof result.data !== "object") {
    return { ok: false, error: { kind: "malformed", message: "Could not parse progression overview." } };
  }
  const o = result.data as Record<string, unknown>;
  const top5Raw = Array.isArray(o.top_5_tricks) ? o.top_5_tricks : [];
  const top_5_tricks = top5Raw
    .filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object")
    .map((row) => ({
      trick_name: typeof row.trick_name === "string" ? row.trick_name : "unknown",
      attempts: typeof row.attempts === "number" ? row.attempts : 0,
      makes: typeof row.makes === "number" ? row.makes : 0,
      percentage: typeof row.percentage === "number" ? row.percentage : 0,
    }));

  return {
    ok: true,
    status: result.status,
    data: {
      total_sessions: typeof o.total_sessions === "number" ? o.total_sessions : 0,
      total_attempts: typeof o.total_attempts === "number" ? o.total_attempts : 0,
      total_makes: typeof o.total_makes === "number" ? o.total_makes : 0,
      global_make_rate: typeof o.global_make_rate === "number" ? o.global_make_rate : 0,
      total_tricks_attempted:
        typeof o.total_tricks_attempted === "number" ? o.total_tricks_attempted : 0,
      top_5_tricks,
      recent_activity: Array.isArray(o.recent_activity)
        ? (o.recent_activity as Array<Record<string, unknown>>)
        : [],
      current_streak: typeof o.current_streak === "number" ? o.current_streak : 0,
      longest_streak: typeof o.longest_streak === "number" ? o.longest_streak : 0,
      sessions_this_week: typeof o.sessions_this_week === "number" ? o.sessions_this_week : 0,
      most_recent_session_id:
        typeof o.most_recent_session_id === "string" ? o.most_recent_session_id : null,
    },
  };
}

export async function fetchWhatsNext(): Promise<ApiResult<WhatsNextPayload>> {
  const result = await apiRequest<unknown>("/api/v1/stats/progression/whats-next", { auth: true });
  if (!result.ok) return result;
  if (!result.data || typeof result.data !== "object") {
    return { ok: false, error: { kind: "malformed", message: "Could not parse what's next." } };
  }
  const o = result.data as Record<string, unknown>;
  return {
    ok: true,
    status: result.status,
    data: {
      has_recommendation: o.has_recommendation === true,
      focus_trick: typeof o.focus_trick === "string" ? o.focus_trick : null,
      focus_issue_key: typeof o.focus_issue_key === "string" ? o.focus_issue_key : null,
      focus_issue_label: typeof o.focus_issue_label === "string" ? o.focus_issue_label : null,
      focus_drill: typeof o.focus_drill === "string" ? o.focus_drill : null,
      focus_cue: typeof o.focus_cue === "string" ? o.focus_cue : null,
      issue_frequency: typeof o.issue_frequency === "number" ? o.issue_frequency : 0,
      window_attempts: typeof o.window_attempts === "number" ? o.window_attempts : 0,
      window_sessions: typeof o.window_sessions === "number" ? o.window_sessions : 0,
      confidence: typeof o.confidence === "string" ? o.confidence : "none",
      message:
        typeof o.message === "string"
          ? o.message
          : "Upload some clips so P.T.E. Tech can start tracking your progression.",
    },
  };
}

export async function fetchTrickStats(): Promise<ApiResult<TrickStatSummary[]>> {
  const result = await apiRequest<unknown>("/api/v1/stats/tricks", { auth: true });
  if (!result.ok) return result;
  if (!Array.isArray(result.data)) {
    return { ok: false, error: { kind: "malformed", message: "Could not parse trick stats." } };
  }
  const items: TrickStatSummary[] = [];
  for (const raw of result.data) {
    if (!raw || typeof raw !== "object") continue;
    const o = raw as Record<string, unknown>;
    if (typeof o.trick_name !== "string") continue;
    items.push({
      trick_name: o.trick_name,
      attempts: typeof o.attempts === "number" ? o.attempts : 0,
      makes: typeof o.makes === "number" ? o.makes : 0,
      percentage: typeof o.percentage === "number" ? o.percentage : 0,
      last_attempted:
        typeof o.last_attempted === "string"
          ? o.last_attempted
          : typeof o.last_attempt_at === "string"
            ? o.last_attempt_at
            : new Date(0).toISOString(),
      trend_last_5_make_rate:
        typeof o.trend_last_5_make_rate === "number" ? o.trend_last_5_make_rate : null,
    });
  }
  return { ok: true, status: result.status, data: items };
}
