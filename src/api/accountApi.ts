import { apiRequest } from "./client";
import type { ApiResult } from "./types";

export type AccountDeletionResponse = {
  status: string;
  message: string;
};

export type AccountExportPayload = {
  user: { id: string; email: string; tier: string };
  consent: unknown;
  clips: unknown[];
  consent_events: unknown[];
  export_generated_at: string;
  policy_version_at_export: string;
};

function parseDeletionResponse(raw: unknown): AccountDeletionResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const status = typeof o.status === "string" ? o.status : "";
  const message = typeof o.message === "string" ? o.message : "";
  if (!status) return null;
  return { status, message };
}

/**
 * Request permanent account deletion (202 Accepted).
 * Server anonymizes the user, purges owned rows, and queues media hard-delete.
 */
export async function deleteMyAccount(): Promise<ApiResult<AccountDeletionResponse>> {
  const result = await apiRequest<unknown>("/api/v1/account", {
    method: "DELETE",
    auth: true,
  });
  if (!result.ok) return result;

  const parsed = parseDeletionResponse(result.data);
  if (!parsed) {
    // 202 with empty body still counts as success for some gateways
    return {
      ok: true,
      data: {
        status: "queued",
        message: "Account deletion queued.",
      },
      status: result.status,
    };
  }
  return { ok: true, data: parsed, status: result.status };
}

/** Download a JSON export of the signed-in user's account data. */
export async function exportMyData(): Promise<ApiResult<AccountExportPayload>> {
  const result = await apiRequest<unknown>("/api/v1/account/export", {
    method: "GET",
    auth: true,
  });
  if (!result.ok) return result;

  if (!result.data || typeof result.data !== "object") {
    return {
      ok: false,
      error: {
        kind: "malformed",
        message: "Export response was not an object.",
        status: result.status,
      },
    };
  }

  const o = result.data as Record<string, unknown>;
  const clips = Array.isArray(o.clips) ? o.clips : [];
  return {
    ok: true,
    data: {
      user: (o.user as AccountExportPayload["user"]) ?? { id: "", email: "", tier: "" },
      consent: o.consent,
      clips,
      consent_events: Array.isArray(o.consent_events) ? o.consent_events : [],
      export_generated_at:
        typeof o.export_generated_at === "string" ? o.export_generated_at : "",
      policy_version_at_export:
        typeof o.policy_version_at_export === "string" ? o.policy_version_at_export : "",
    },
    status: result.status,
  };
}
