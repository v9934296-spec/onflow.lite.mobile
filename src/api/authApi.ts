import { apiRequest } from "./client";
import type { AccountMe, AuthSignInResult, ConsentStatus } from "../types/api/account";
import type { ApiResult } from "./types";

function parseConsentStatus(raw: unknown): ConsentStatus {
  if (!raw || typeof raw !== "object") {
    return { granted: false, granted_at: null, copy_version: null, source: null };
  }
  const o = raw as Record<string, unknown>;
  return {
    granted: o.granted === true,
    granted_at: typeof o.granted_at === "string" ? o.granted_at : null,
    copy_version: typeof o.copy_version === "string" ? o.copy_version : null,
    source: typeof o.source === "string" ? o.source : null,
  };
}

export function parseAccountMe(raw: unknown): AccountMe | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const userId = typeof o.user_id === "string" ? o.user_id.trim() : "";
  if (!userId) return null;
  const email = typeof o.email === "string" ? o.email.trim() : "";
  return {
    user_id: userId,
    email,
    tier: typeof o.tier === "string" ? o.tier : "free",
    profile_image_url: typeof o.profile_image_url === "string" ? o.profile_image_url : null,
    theme_preference:
      o.theme_preference === "system" || o.theme_preference === "light" || o.theme_preference === "dark"
        ? o.theme_preference
        : undefined,
    consent: parseConsentStatus(o.consent),
    bonus_analyses_remaining:
      typeof o.bonus_analyses_remaining === "number" ? o.bonus_analyses_remaining : null,
    monthly_free_remaining:
      typeof o.monthly_free_remaining === "number" ? o.monthly_free_remaining : null,
  };
}

function parseOAuthSession(raw: unknown, fallbackEmail?: string | null): AuthSignInResult | null {
  if (!raw || typeof raw !== "object") return null;
  const rec = raw as Record<string, unknown>;
  const token = typeof rec.token === "string" ? rec.token.trim() : "";
  const userId = typeof rec.user_id === "string" ? rec.user_id.trim() : "";
  if (!token || !userId) return null;
  const backendEmail = typeof rec.email === "string" ? rec.email.trim().toLowerCase() : "";
  const fallback = (fallbackEmail ?? "").trim().toLowerCase();
  return {
    session: { token, userId, email: backendEmail || fallback },
    isNewUser: rec.is_new_user === true,
    bonusAnalysesRemaining:
      typeof rec.bonus_analyses_remaining === "number" ? rec.bonus_analyses_remaining : 0,
  };
}

function parseEmailSession(raw: unknown, email: string): AuthSignInResult | null {
  if (!raw || typeof raw !== "object") return null;
  const rec = raw as Record<string, unknown>;
  const token =
    typeof rec.session_token === "string"
      ? rec.session_token
      : typeof rec.sessionToken === "string"
        ? rec.sessionToken
        : null;
  const userId =
    typeof rec.user_id === "string" ? rec.user_id : typeof rec.userId === "string" ? rec.userId : null;
  const normEmail = typeof rec.email === "string" ? rec.email : email.trim().toLowerCase();
  if (!token?.trim() || !userId?.trim()) return null;
  return {
    session: { token: token.trim(), userId: userId.trim(), email: normEmail },
  };
}

export async function createEmailSession(email: string): Promise<ApiResult<AuthSignInResult>> {
  const body = { email: email.trim() };

  const result = await apiRequest<unknown>("/api/v1/auth/session", {
    method: "POST",
    body,
  });
  if (!result.ok) return result;

  const parsed = parseEmailSession(result.data, email);
  if (!parsed) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Server session response was missing token or user id." },
    };
  }
  return { ok: true, data: parsed, status: result.status };
}

export async function signInWithGoogle(
  idToken: string,
  fallbackEmail?: string | null,
): Promise<ApiResult<AuthSignInResult>> {
  const result = await apiRequest<unknown>("/api/v1/auth/google", {
    method: "POST",
    body: { id_token: idToken },
  });
  if (!result.ok) return result;

  const parsed = parseOAuthSession(result.data, fallbackEmail);
  if (!parsed) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Google sign-in response was missing token or user id." },
    };
  }
  return { ok: true, data: parsed, status: result.status };
}

export async function signInWithApple(
  idToken: string,
  fallbackEmail?: string | null,
): Promise<ApiResult<AuthSignInResult>> {
  const result = await apiRequest<unknown>("/api/v1/auth/apple", {
    method: "POST",
    body: { id_token: idToken },
  });
  if (!result.ok) return result;

  const parsed = parseOAuthSession(result.data, fallbackEmail);
  if (!parsed) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Apple sign-in response was missing token or user id." },
    };
  }
  return { ok: true, data: parsed, status: result.status };
}

export async function fetchAccountMe(): Promise<ApiResult<AccountMe>> {
  const result = await apiRequest<unknown>("/api/v1/account/me", { auth: true });
  if (!result.ok) return result;

  const parsed = parseAccountMe(result.data);
  if (!parsed) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Account response was missing user_id." },
    };
  }
  return { ok: true, data: parsed, status: result.status };
}
