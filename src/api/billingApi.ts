import { apiRequest } from "./client";
import type { ApiResult } from "./types";

export type BillingSyncPayload = {
  has_pro: boolean;
  sync_tier?: "pro" | null;
  bonus_purchased?: number;
  rc_app_user_id?: string | null;
};

export type BillingSyncResponse = {
  tier: string;
  bonus_analyses: number;
  monthly_free_remaining: number | null;
};

function parseBillingSyncResponse(raw: unknown): BillingSyncResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const tier = typeof o.tier === "string" ? o.tier : "";
  if (!tier) return null;
  return {
    tier,
    bonus_analyses: typeof o.bonus_analyses === "number" ? o.bonus_analyses : 0,
    monthly_free_remaining:
      typeof o.monthly_free_remaining === "number" ? o.monthly_free_remaining : null,
  };
}

/** Push store entitlement state to backend after purchase/restore (Phase 11 hook). */
export async function syncBillingToBackend(
  payload: BillingSyncPayload,
): Promise<ApiResult<BillingSyncResponse>> {
  const result = await apiRequest<unknown>("/api/v1/billing/sync", {
    method: "POST",
    auth: true,
    body: {
      has_pro: payload.has_pro,
      sync_tier: payload.sync_tier ?? null,
      bonus_purchased: payload.bonus_purchased ?? 0,
      rc_app_user_id: payload.rc_app_user_id ?? null,
    },
  });
  if (!result.ok) return result;

  const parsed = parseBillingSyncResponse(result.data);
  if (!parsed) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Billing sync response was missing tier.", status: result.status },
    };
  }
  return { ok: true, data: parsed, status: result.status };
}
