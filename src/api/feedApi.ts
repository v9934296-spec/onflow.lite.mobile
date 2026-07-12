import { apiRequest } from "./client";
import type { FeedResponse } from "../types/api/feed";
import type {
  FeedEvent,
  FeedEventPayload,
  FeedEventType,
  ReactionsSummary,
} from "../types/feedEvent";
import type { ApiResult } from "./types";

const REACTION_TYPES = ["fire", "saw_it", "same_battle", "progression"] as const;

function emptyReactions(): ReactionsSummary {
  const bucket = { count: 0, viewer_reacted: false, reactor_user_ids: [] as string[] };
  return {
    fire: { ...bucket },
    saw_it: { ...bucket },
    same_battle: { ...bucket },
    progression: { ...bucket },
  };
}

function parseReactions(raw: unknown): ReactionsSummary {
  if (!raw || typeof raw !== "object") return emptyReactions();
  const o = raw as Record<string, unknown>;
  const out = emptyReactions();
  for (const key of REACTION_TYPES) {
    const b = o[key];
    if (!b || typeof b !== "object") continue;
    const row = b as Record<string, unknown>;
    out[key] = {
      count: typeof row.count === "number" ? row.count : 0,
      viewer_reacted: row.viewer_reacted === true,
      reactor_user_ids: Array.isArray(row.reactor_user_ids)
        ? row.reactor_user_ids.filter((x): x is string => typeof x === "string")
        : [],
    };
  }
  return out;
}

export function parseFeedEvent(raw: unknown): FeedEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const id = typeof o.id === "string" ? o.id : null;
  const eventType = typeof o.event_type === "string" ? o.event_type : null;
  const eventVersion = typeof o.event_version === "string" ? o.event_version : null;
  const generatedAt = typeof o.generated_at === "string" ? o.generated_at : null;
  if (!id || !eventType || !eventVersion || !generatedAt) return null;

  const userRaw = o.user;
  if (!userRaw || typeof userRaw !== "object") return null;
  const u = userRaw as Record<string, unknown>;
  const userId = typeof u.user_id === "string" ? u.user_id : null;
  if (!userId) return null;

  const tierRaw = typeof u.tier === "string" ? u.tier : "flow";
  const tier =
    tierRaw === "pro" || tierRaw === "flow_plus" || tierRaw === "flow" ? tierRaw : "flow";

  const payload =
    o.payload && typeof o.payload === "object" ? (o.payload as FeedEventPayload) : null;
  if (!payload) return null;

  return {
    id,
    user: {
      user_id: userId,
      username: typeof u.username === "string" ? u.username : userId,
      tag_name: typeof u.tag_name === "string" ? u.tag_name : "Skater",
      profile_photo_url: typeof u.profile_photo_url === "string" ? u.profile_photo_url : null,
      tier,
    },
    event_type: eventType as FeedEventType,
    event_version: eventVersion,
    payload,
    generated_at: generatedAt,
    reactions_summary: parseReactions(o.reactions_summary),
  };
}

export function parseFeedResponse(raw: unknown): FeedResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const stage = o.lifecycle_stage;
  if (stage !== "stage_a" && stage !== "stage_b" && stage !== "stage_c") return null;
  const itemsRaw = Array.isArray(o.items) ? o.items : [];
  const items = itemsRaw
    .map((row) => parseFeedEvent(row))
    .filter((e): e is FeedEvent => e != null);
  return {
    items,
    next_cursor: typeof o.next_cursor === "string" ? o.next_cursor : null,
    lifecycle_stage: stage,
  };
}

export async function fetchFeed(params: {
  limit?: number;
  cursor?: string | null;
}): Promise<ApiResult<FeedResponse>> {
  const limit = params.limit ?? 20;
  const qs = new URLSearchParams({ limit: String(limit) });
  if (params.cursor) qs.set("cursor", params.cursor);

  const result = await apiRequest<unknown>(`/api/v1/feed?${qs.toString()}`, { auth: true });
  if (!result.ok) return result;

  const parsed = parseFeedResponse(result.data);
  if (!parsed) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Could not read feed response.", status: result.status },
    };
  }
  return { ok: true, data: parsed, status: result.status };
}
