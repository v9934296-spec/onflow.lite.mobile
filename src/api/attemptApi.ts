import { apiRequest } from "./client";
import type { SessionAttempt } from "../types/sessionAttempt";
import type { ApiResult } from "./types";

export type SessionAttemptSyncResponse = {
  accepted: string[];
  rejected: Array<{ id: string; reason: string }>;
};

function parseSyncResponse(raw: unknown): SessionAttemptSyncResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const accepted = Array.isArray(o.accepted)
    ? o.accepted.filter((x): x is string => typeof x === "string")
    : [];
  const rejected = Array.isArray(o.rejected)
    ? o.rejected
        .filter((x): x is Record<string, unknown> => !!x && typeof x === "object")
        .map((x) => ({
          id: typeof x.id === "string" ? x.id : "",
          reason: typeof x.reason === "string" ? x.reason : "unknown",
        }))
        .filter((x) => x.id)
    : [];
  return { accepted, rejected };
}

function parseAttempt(raw: unknown): SessionAttempt | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const id = typeof o.id === "string" ? o.id : "";
  const sessionId = typeof o.session_id === "string" ? o.session_id : "";
  const trickId = typeof o.trick_id === "string" ? o.trick_id : "";
  const canonicalName = typeof o.canonical_name === "string" ? o.canonical_name : "";
  const outcome = o.outcome === "landed" || o.outcome === "missed" ? o.outcome : null;
  const loggedAt = typeof o.logged_at === "string" ? o.logged_at : "";
  if (!id || !sessionId || !trickId || !canonicalName || !outcome || !loggedAt) return null;
  return { id, sessionId, trickId, canonicalName, outcome, loggedAt };
}

/** Batch upsert client-logged attempts (offline outbox flush). */
export async function syncSessionAttempts(
  attempts: SessionAttempt[],
): Promise<ApiResult<SessionAttemptSyncResponse>> {
  const result = await apiRequest<unknown>("/api/v1/session-attempts/sync", {
    method: "POST",
    auth: true,
    body: {
      attempts: attempts.map((a) => ({
        id: a.id,
        session_id: a.sessionId,
        trick_id: a.trickId,
        canonical_name: a.canonicalName,
        outcome: a.outcome,
        logged_at: a.loggedAt,
      })),
    },
  });
  if (!result.ok) return result;
  const parsed = parseSyncResponse(result.data);
  if (!parsed) {
    return {
      ok: false,
      error: {
        kind: "malformed",
        message: "Attempt sync response was malformed.",
        status: result.status,
      },
    };
  }
  return { ok: true, data: parsed, status: result.status };
}

/** Fetch server attempts for a session (merge with local on hydrate). */
export async function fetchSessionAttempts(
  sessionId: string,
): Promise<ApiResult<SessionAttempt[]>> {
  const sid = sessionId.trim();
  if (!sid) {
    return { ok: true, data: [], status: 200 };
  }
  const result = await apiRequest<unknown>(`/api/v1/sessions/${encodeURIComponent(sid)}/attempts`, {
    method: "GET",
    auth: true,
  });
  if (!result.ok) return result;
  const o = result.data && typeof result.data === "object" ? (result.data as Record<string, unknown>) : {};
  const list = Array.isArray(o.attempts) ? o.attempts : [];
  const attempts = list.map(parseAttempt).filter((a): a is SessionAttempt => a != null);
  return { ok: true, data: attempts, status: result.status };
}
