import { mergeApiTelemetryHeaders } from "./telemetry";

export type AuthTokenProvider = () => Promise<string | null>;

let authTokenProvider: AuthTokenProvider | null = null;
let onAuthExpired: (() => void) | null = null;

/** Register a token provider (Phase 2 will supply real auth storage). */
export function setAuthTokenProvider(provider: AuthTokenProvider | null): void {
  authTokenProvider = provider;
}

/** Register a callback that fires when any authed API call gets a 401. */
export function setAuthExpiredCallback(cb: (() => void) | null): void {
  onAuthExpired = cb;
}

/** Fire the registered auth-expired callback if the response is a 401. */
export function notifyAuthExpiredOn401(res: Response): void {
  if (res.status === 401 && onAuthExpired) {
    onAuthExpired();
  }
}

export async function buildAuthHeaders(): Promise<Record<string, string> | null> {
  if (!authTokenProvider) return null;
  const token = await authTokenProvider();
  if (!token?.trim()) return null;
  return mergeApiTelemetryHeaders({ Authorization: `Bearer ${token.trim()}` });
}

/** Reset providers — for tests only. */
export function resetAuthHooks(): void {
  authTokenProvider = null;
  onAuthExpired = null;
}
