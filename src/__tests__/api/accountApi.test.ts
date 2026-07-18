import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: { version: "1.0.0", ios: { buildNumber: "1" } },
    nativeBuildVersion: "1",
  },
}));

import { deleteMyAccount, exportMyData } from "../../api/accountApi";
import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";

describe("accountApi", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "test-token");
  });

  afterEach(() => {
    if (originalUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = originalUrl;
    fetchMock.mockReset();
    resetAuthHooks();
  });

  it("DELETEs /api/v1/account and parses 202 body", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "queued",
          message: "Account deletion queued. Your clips will be permanently removed within 24 hours.",
        }),
        { status: 202 },
      ),
    );

    const res = await deleteMyAccount();
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.status).toBe("queued");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/account");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
  });

  it("GETs /api/v1/account/export", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          user: { id: "u1", email: "a@b.c", tier: "free" },
          consent: { granted: true },
          clips: [{ job_id: "j1" }],
          consent_events: [],
          export_generated_at: "2026-01-01T00:00:00Z",
          policy_version_at_export: "v1",
        }),
        { status: 200 },
      ),
    );

    const res = await exportMyData();
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.clips).toHaveLength(1);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/account/export");
  });
});
