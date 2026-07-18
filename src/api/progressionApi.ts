import { apiRequest } from "./client";
import type { ApiResult } from "./types";

export type ProgressionTimelineItem = {
  session_id: string;
  ended_at: string | null;
  spot: string | null;
  focus_trick: string | null;
  duration_seconds: number | null;
  clips_count: number;
  best_pte_score: number | null;
  thumbnail_url: string | null;
};

export type ProgressionTimelineResponse = {
  items: ProgressionTimelineItem[];
  page: number;
  page_size: number;
  has_more: boolean;
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
    best_pte_score: typeof o.best_pte_score === "number" ? o.best_pte_score : null,
    thumbnail_url: typeof o.thumbnail_url === "string" ? o.thumbnail_url : null,
  };
}

export async function fetchProgressionTimeline(page = 1, pageSize = 20): Promise<ApiResult<ProgressionTimelineResponse>> {
  const result = await apiRequest<unknown>(`/api/v1/progression/timeline?page=${page}&page_size=${pageSize}`, { auth: true });
  if (!result.ok) return result;
  if (!result.data || typeof result.data !== "object") return { ok: false, error: { kind: "malformed", message: "Could not parse progression timeline." } };
  const o = result.data as Record<string, unknown>;
  const items = Array.isArray(o.items) ? o.items.map(parseItem).filter((item): item is ProgressionTimelineItem => Boolean(item)) : [];
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
