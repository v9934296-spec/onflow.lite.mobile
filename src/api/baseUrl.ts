import { Platform } from "react-native";

import { getRawExpoApiUrl } from "./config";

/**
 * Android/native: uses EXPO_PUBLIC_API_URL as-is (LAN IP, 10.0.2.2, etc.).
 *
 * Web: pages are served from localhost; fetching another RFC1918 address (e.g. 192.168.x.x)
 * often fails (browser private-network / hairpin rules). If EXPO_PUBLIC_API_URL points at a
 * private host, we use 127.0.0.1 with the same port — correct when the API runs on this PC.
 * Set EXPO_PUBLIC_API_URL_WEB when the API is on a *different* machine on the LAN.
 */
export function getApiBaseUrl(): string {
  const raw = getRawExpoApiUrl();
  const cleaned = raw.replace(/\/$/, "");

  if (Platform.OS !== "web") {
    return cleaned;
  }

  const webOverride = (process.env.EXPO_PUBLIC_API_URL_WEB ?? "").trim().replace(/\/$/, "");
  if (webOverride) {
    return webOverride;
  }

  if (!cleaned) {
    return "http://127.0.0.1:8000";
  }

  try {
    const url = new URL(cleaned.includes("://") ? cleaned : `http://${cleaned}`);
    const host = url.hostname.toLowerCase();
    const isLan =
      /^192\.168\./.test(host) || /^10\./.test(host) || /^172\.(1[6-9]|2\d|3[01])\./.test(host);
    if (isLan) {
      const port =
        url.port || (url.protocol === "https:" ? "443" : url.protocol === "http:" ? "80" : "");
      const scheme = url.protocol === "https:" ? "https" : "http";
      return port ? `${scheme}://127.0.0.1:${port}` : `${scheme}://127.0.0.1`;
    }
  } catch {
    /* use cleaned */
  }

  return cleaned;
}
