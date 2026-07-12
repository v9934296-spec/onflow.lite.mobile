import { createEmailSession } from "../api/authApi";
import { saveOnflowSession } from "./onflowSession";

const TRUTHY = new Set(["1", "true", "yes", "on"]);

export function isDevSkipSignInEnabled(): boolean {
  if (typeof __DEV__ === "undefined" || !__DEV__) return false;
  const v = (process.env.EXPO_PUBLIC_DEV_SKIP_SIGN_IN ?? "").trim().toLowerCase();
  return TRUTHY.has(v);
}

export function devAutoSignInEmail(): string {
  const raw = process.env.EXPO_PUBLIC_DEV_AUTO_EMAIL?.trim();
  if (raw && raw.includes("@")) return raw;
  return "e2e-dev@onflow.local";
}

export async function bootstrapDevSessionIfNeeded(): Promise<{ ok: boolean; error?: string }> {
  try {
    const email = devAutoSignInEmail();
    const result = await createEmailSession(email);
    if (!result.ok) {
      return { ok: false, error: result.error.message };
    }
    await saveOnflowSession(result.data.session);
    return { ok: true };
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Session bootstrap failed.";
    return { ok: false, error: msg };
  }
}

