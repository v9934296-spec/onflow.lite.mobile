import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";
import { apiRequest } from "../../api/client";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: { version: "1.0.0", ios: { buildNumber: "1" } },
    nativeBuildVersion: "1",
  },
}));

describe("apiRequest", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
  });

  afterEach(() => {
    if (originalUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL;
    } else {
      process.env.EXPO_PUBLIC_API_URL = originalUrl;
    }
    fetchMock.mockReset();
    resetAuthHooks();
  });

  it("returns configuration error when URL is missing", async () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    const result = await apiRequest("/health");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("configuration");
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("attaches telemetry headers", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    await apiRequest("/health");
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["X-App-Version"]).toBe("1.0.0");
    expect(headers["X-Platform"]).toBe("ios");
  });

  it("injects Authorization when auth provider is set", async () => {
    setAuthTokenProvider(async () => "test-token");
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    await apiRequest("/api/v1/account/me", { auth: true });
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("returns unauthorized when auth is required but no token", async () => {
    const result = await apiRequest("/api/v1/account/me", { auth: true });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("unauthorized");
    }
  });

  it("classifies 401 as unauthorized", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid token" }), { status: 401 }),
    );
    const result = await apiRequest("/health");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("unauthorized");
      expect(result.error.detail).toBe("Invalid token");
    }
  });

  it("classifies 404 as client error", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
    );
    const result = await apiRequest("/missing");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("client");
      expect(result.error.status).toBe(404);
    }
  });

  it("classifies 503 as server error", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "db_unreachable" }), { status: 503 }),
    );
    const result = await apiRequest("/health");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("server");
      expect(result.error.status).toBe(503);
    }
  });

  it("classifies network failures", async () => {
    fetchMock.mockRejectedValue(new Error("Network request failed"));
    const result = await apiRequest("/health");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("network");
    }
  });

  it("classifies timeout via AbortError", async () => {
    const abortErr = new Error("aborted");
    abortErr.name = "AbortError";
    fetchMock.mockRejectedValue(abortErr);
    const result = await apiRequest("/health", { timeoutMs: 1 });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("timeout");
    }
  });

  it("classifies non-JSON success body as malformed", async () => {
    fetchMock.mockResolvedValue(new Response("not json", { status: 200 }));
    const result = await apiRequest("/health");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe("malformed");
    }
  });
});
