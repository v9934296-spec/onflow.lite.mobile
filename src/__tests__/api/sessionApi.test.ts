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

import { createSkateSession, fetchSkateSession, parseSkateSession } from "../../api/sessionApi";
import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";

const SAMPLE_SESSION = {
  id: "sess-1",
  user_id: "user-1",
  spot_label: "Park ledge",
  focus_trick: "Kickflip",
  notes: null,
  started_at: "2026-07-11T12:00:00Z",
  ended_at: null,
  breakthrough_note: null,
  clip_count: 0,
  attempt_count: 0,
  created_at: "2026-07-11T12:00:00Z",
  updated_at: "2026-07-11T12:00:00Z",
  deleted_at: null,
};

describe("parseSkateSession", () => {
  it("parses a valid session response", () => {
    expect(parseSkateSession(SAMPLE_SESSION)).toEqual(SAMPLE_SESSION);
  });

  it("rejects missing id or user_id", () => {
    expect(parseSkateSession({ user_id: "u1" })).toBeNull();
    expect(parseSkateSession(null)).toBeNull();
  });

  it("falls back cached count fields", () => {
    const parsed = parseSkateSession({
      ...SAMPLE_SESSION,
      clip_count: undefined,
      attempt_count: undefined,
      clip_count_cached: 3,
      attempt_count_cached: 5,
    });
    expect(parsed?.clip_count).toBe(3);
    expect(parsed?.attempt_count).toBe(5);
  });
});

describe("sessionApi", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "test-token");
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

  it("creates a session via POST /api/v1/sessions", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(SAMPLE_SESSION), { status: 201 }),
    );
    const result = await createSkateSession({ spot_label: "Park ledge" });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.id).toBe("sess-1");
    }
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.example.com/api/v1/sessions");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body).toEqual({ spot_label: "Park ledge" });
  });

  it("prevents duplicate create calls from sharing auth headers", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(SAMPLE_SESSION), { status: 201 }),
    );
    await createSkateSession();
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("fetches a session by id", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(SAMPLE_SESSION), { status: 200 }),
    );
    const result = await fetchSkateSession("sess-1");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data?.id).toBe("sess-1");
    }
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/sessions/sess-1");
  });

  it("returns null data for 404 session", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
    );
    const result = await fetchSkateSession("missing");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toBeNull();
      expect(result.status).toBe(404);
    }
  });
});
