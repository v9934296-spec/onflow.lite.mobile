import { apiRequest } from "./client";
import type { ApiResult } from "./types";
import type {
  CreateSkateSessionRequest,
  SkateSession,
  UpdateSkateSessionRequest,
} from "../types/api/session";

function normalizeOptional(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

function requiredString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function requiredTimestamp(value: unknown): string | null {
  const text = requiredString(value);
  return text && Number.isFinite(Date.parse(text)) ? text : null;
}

function optionalTimestamp(value: unknown): string | null {
  if (value == null) return null;
  return requiredTimestamp(value);
}

function requiredCount(primary: unknown, cached: unknown): number | null {
  const value = typeof primary === "number" ? primary : typeof cached === "number" ? cached : null;
  return value != null && Number.isInteger(value) && value >= 0 ? value : null;
}

export function parseSkateSession(raw: unknown): SkateSession | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const id = requiredString(o.id);
  const userId = requiredString(o.user_id);
  const startedAt = requiredTimestamp(o.started_at);
  const createdAt = requiredTimestamp(o.created_at);
  const updatedAt = requiredTimestamp(o.updated_at);
  const clipCount = requiredCount(o.clip_count, o.clip_count_cached);
  const attemptCount = requiredCount(o.attempt_count, o.attempt_count_cached);

  if (!id || !userId || !startedAt || !createdAt || !updatedAt || clipCount == null || attemptCount == null) {
    return null;
  }

  const endedAt = optionalTimestamp(o.ended_at);
  if (o.ended_at != null && !endedAt) return null;
  const deletedAt = optionalTimestamp(o.deleted_at);
  if (o.deleted_at != null && !deletedAt) return null;

  return {
    id,
    user_id: userId,
    spot_label: typeof o.spot_label === "string" ? normalizeOptional(o.spot_label) : null,
    focus_trick: typeof o.focus_trick === "string" ? normalizeOptional(o.focus_trick) : null,
    notes: typeof o.notes === "string" ? normalizeOptional(o.notes) : null,
    started_at: startedAt,
    ended_at: endedAt,
    breakthrough_note:
      typeof o.breakthrough_note === "string" ? normalizeOptional(o.breakthrough_note) : null,
    clip_count: clipCount,
    attempt_count: attemptCount,
    created_at: createdAt,
    updated_at: updatedAt,
    deleted_at: deletedAt,
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
