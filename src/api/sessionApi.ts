import type { ApiResult } from "./types";
import { apiRequest } from "./client";
import type {
  CreateSkateSessionRequest,
  SkateSession,
  UpdateSkateSessionRequest,
} from "../types/api/session";

function normalizeOptional(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

export function parseSkateSession(raw: unknown): SkateSession | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const id = typeof o.id === "string" ? o.id : null;
  const userId = typeof o.user_id === "string" ? o.user_id : null;
  if (!id || !userId) return null;

  const clipCount =
    typeof o.clip_count === "number"
      ? o.clip_count
      : typeof o.clip_count_cached === "number"
        ? o.clip_count_cached
        : 0;
  const attemptCount =
    typeof o.attempt_count === "number"
      ? o.attempt_count
      : typeof o.attempt_count_cached === "number"
        ? o.attempt_count_cached
        : clipCount;

  return {
    id,
    user_id: userId,
    spot_label: typeof o.spot_label === "string" ? o.spot_label : null,
    focus_trick: typeof o.focus_trick === "string" ? o.focus_trick : null,
    notes: typeof o.notes === "string" ? o.notes : null,
    started_at: typeof o.started_at === "string" ? o.started_at : new Date().toISOString(),
    ended_at: typeof o.ended_at === "string" ? o.ended_at : null,
    breakthrough_note: typeof o.breakthrough_note === "string" ? o.breakthrough_note : null,
    clip_count: clipCount,
    attempt_count: attemptCount,
    created_at: typeof o.created_at === "string" ? o.created_at : new Date().toISOString(),
    updated_at:
      typeof o.updated_at === "string"
        ? o.updated_at
        : typeof o.created_at === "string"
          ? o.created_at
          : new Date().toISOString(),
    deleted_at: typeof o.deleted_at === "string" ? o.deleted_at : null,
  };
}

export async function createSkateSession(
  req: CreateSkateSessionRequest = {},
): Promise<ApiResult<SkateSession>> {
  const body: Record<string, string> = {};
  const spot = normalizeOptional(req.spot_label);
  const focus = normalizeOptional(req.focus_trick);
  const notes = normalizeOptional(req.notes);
  if (spot) body.spot_label = spot;
  if (focus) body.focus_trick = focus;
  if (notes) body.notes = notes;

  const result = await apiRequest<unknown>("/api/v1/sessions", {
    method: "POST",
    auth: true,
    body,
  });
  if (!result.ok) return result;

  const session = parseSkateSession(result.data);
  if (!session) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Could not parse session from server." },
    };
  }
  return { ok: true, data: session, status: result.status };
}

export async function updateSkateSession(
  sessionId: string,
  patch: UpdateSkateSessionRequest,
): Promise<ApiResult<SkateSession>> {
  const body: Record<string, string> = {};
  const spot = normalizeOptional(patch.spot_label);
  const focus = normalizeOptional(patch.focus_trick);
  const notes = normalizeOptional(patch.notes);
  const breakthrough = normalizeOptional(patch.breakthrough_note);
  if (spot) body.spot_label = spot;
  if (focus) body.focus_trick = focus;
  if (notes) body.notes = notes;
  if (breakthrough) body.breakthrough_note = breakthrough;
  if (patch.ended_at) body.ended_at = patch.ended_at;

  const result = await apiRequest<unknown>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}`,
    { method: "PATCH", auth: true, body },
  );
  if (!result.ok) return result;

  const session = parseSkateSession(result.data);
  if (!session) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Could not parse session from server." },
    };
  }
  return { ok: true, data: session, status: result.status };
}

export async function fetchSkateSession(sessionId: string): Promise<ApiResult<SkateSession | null>> {
  const result = await apiRequest<unknown>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}`,
    { auth: true },
  );

  if (!result.ok) {
    if (result.error.status === 404) {
      return { ok: true, data: null, status: 404 };
    }
    return result;
  }

  const session = parseSkateSession(result.data);
  if (!session) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Could not parse session from server." },
    };
  }
  return { ok: true, data: session, status: result.status };
}
