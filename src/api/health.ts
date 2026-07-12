import { apiRequest } from "./client";
import type { ApiResult, HealthResponse } from "./types";

export function parseHealthResponse(raw: unknown): HealthResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (typeof obj.status !== "string" || !obj.status.trim()) return null;

  const health: HealthResponse = { status: obj.status.trim() };

  if (typeof obj.db === "string") health.db = obj.db;
  if (typeof obj.gemini_configured === "boolean") health.gemini_configured = obj.gemini_configured;
  if (typeof obj.twelvelabs_configured === "boolean") {
    health.twelvelabs_configured = obj.twelvelabs_configured;
  }
  if (typeof obj.clip_review_ready === "boolean") health.clip_review_ready = obj.clip_review_ready;

  return health;
}

export async function checkHealth(): Promise<ApiResult<HealthResponse>> {
  const result = await apiRequest<unknown>("/health");

  if (!result.ok) {
    return result;
  }

  const parsed = parseHealthResponse(result.data);
  if (!parsed) {
    return {
      ok: false,
      error: {
        kind: "malformed",
        message: "Health response missing required status field.",
        status: result.status,
      },
    };
  }

  return { ok: true, data: parsed, status: result.status };
}
