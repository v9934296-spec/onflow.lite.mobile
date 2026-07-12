import { Platform } from "react-native";

/**
 * FastAPI often returns { "detail": string | object | array }.
 * Turn that into a single string for UI.
 */
export function formatApiDetail(raw: unknown): string | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "string" && raw.trim()) return raw.trim();
  if (Array.isArray(raw)) {
    const parts = raw.map((item) => {
      if (
        item &&
        typeof item === "object" &&
        "msg" in item &&
        typeof (item as { msg: unknown }).msg === "string"
      ) {
        return (item as { msg: string }).msg;
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    return parts.filter(Boolean).join("; ") || null;
  }
  if (typeof raw === "object") {
    try {
      return JSON.stringify(raw);
    } catch {
      return String(raw);
    }
  }
  return String(raw);
}

export function extractApiErrorBody(json: unknown): string | null {
  if (!json || typeof json !== "object" || !("detail" in json)) return null;
  return formatApiDetail((json as { detail: unknown }).detail);
}

export function networkFailureHint(apiBase: string): string {
  const tail = apiBase ? ` (${apiBase})` : "";
  if (Platform.OS === "web") {
    return [
      `Could not reach API${tail}.`,
      "On web, LAN IPs in .env may be rewritten to 127.0.0.1. If the API is on another device, set EXPO_PUBLIC_API_URL_WEB.",
      "After .env changes, restart Expo with a clear cache.",
    ].join(" ");
  }
  return `Could not reach the OnFlow API${tail}. Check Wi‑Fi or cellular data and try again.`;
}

export function configurationFailureMessage(): string {
  if (typeof __DEV__ !== "undefined" && __DEV__) {
    return "API URL is not configured. Set EXPO_PUBLIC_API_URL in .env and restart Expo.";
  }
  return "This build is missing the server address.";
}

export function isNetworkFetchError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return (
    msg.includes("failed to fetch") ||
    msg.includes("network request failed") ||
    msg.includes("network error")
  );
}

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}
