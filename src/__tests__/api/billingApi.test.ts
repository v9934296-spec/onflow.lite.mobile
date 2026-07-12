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

import { syncBillingToBackend } from "../../api/billingApi";
import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";

describe("billingApi", () => {
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

  it("POSTs billing sync payload", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ tier: "pro", bonus_analyses: 3, monthly_free_remaining: null }),
        { status: 200 },
      ),
    );

    const res = await syncBillingToBackend({ has_pro: true, sync_tier: "pro" });
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.tier).toBe("pro");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/billing/sync");
  });
});
