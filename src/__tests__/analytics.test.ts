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

import { track } from "../analytics";
import { resetAuthHooks, setAuthTokenProvider } from "../api/auth";

describe("analytics track", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "tok");
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
  });

  afterEach(() => {
    if (originalUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = originalUrl;
    fetchMock.mockReset();
    resetAuthHooks();
  });

  it("POSTs allowlisted events to beta client-events", async () => {
    track("home_viewed", { source: "test" });
    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/beta/client-events");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string);
    expect(body.kind).toBe("home_viewed");
  });
});
