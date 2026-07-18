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

import { fetchSessionAttempts, syncSessionAttempts } from "../../api/attemptApi";
import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";

describe("attemptApi", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "tok");
  });

  afterEach(() => {
    if (originalUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = originalUrl;
    fetchMock.mockReset();
    resetAuthHooks();
  });

  it("POSTs batch sync payload", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ accepted: ["a1"], rejected: [] }), { status: 200 }),
    );
    const res = await syncSessionAttempts([
      {
        id: "a1",
        sessionId: "s1",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "landed",
        loggedAt: "2026-07-17T12:00:00Z",
      },
    ]);
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.accepted).toEqual(["a1"]);
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/session-attempts/sync");
  });

  it("GETs session attempts", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          attempts: [
            {
              id: "a1",
              session_id: "s1",
              trick_id: "kickflip",
              canonical_name: "Kickflip",
              outcome: "landed",
              logged_at: "2026-07-17T12:00:00Z",
            },
          ],
        }),
        { status: 200 },
      ),
    );
    const res = await fetchSessionAttempts("s1");
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data[0]?.trickId).toBe("kickflip");
  });
});
