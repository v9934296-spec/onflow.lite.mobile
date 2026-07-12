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

import { fetchFeed, parseFeedEvent, parseFeedResponse } from "../../api/feedApi";
import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";

const SAMPLE_EVENT = {
  id: "evt-1",
  event_type: "first_land",
  event_version: "v1",
  generated_at: "2026-07-11T12:00:00Z",
  user: {
    user_id: "u1",
    username: "vincent",
    tag_name: "Vincent",
    profile_photo_url: null,
    tier: "flow",
  },
  payload: {
    trick_id: "kickflip",
    trick_display: "Kickflip",
    clip_id: "clip-1",
    clip_thumbnail_url: "https://example.com/thumb.jpg",
    attempt_count_prior: 5,
    pte_rating: 7,
  },
  reactions_summary: {
    fire: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
    saw_it: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
    same_battle: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
    progression: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
  },
};

describe("parseFeedEvent", () => {
  it("parses a valid feed event", () => {
    const parsed = parseFeedEvent(SAMPLE_EVENT);
    expect(parsed?.id).toBe("evt-1");
    expect(parsed?.event_type).toBe("first_land");
  });

  it("rejects malformed events", () => {
    expect(parseFeedEvent(null)).toBeNull();
    expect(parseFeedEvent({ id: "x" })).toBeNull();
  });
});

describe("parseFeedResponse", () => {
  it("parses feed page with lifecycle stage", () => {
    const parsed = parseFeedResponse({
      lifecycle_stage: "stage_b",
      items: [SAMPLE_EVENT],
      next_cursor: "cur-2",
    });
    expect(parsed?.lifecycle_stage).toBe("stage_b");
    expect(parsed?.items).toHaveLength(1);
    expect(parsed?.next_cursor).toBe("cur-2");
  });
});

describe("fetchFeed", () => {
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

  it("GETs /api/v1/feed with auth", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          lifecycle_stage: "stage_a",
          items: [],
          next_cursor: null,
        }),
        { status: 200 },
      ),
    );

    const res = await fetchFeed({ limit: 10 });
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.lifecycle_stage).toBe("stage_a");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/feed");
  });
});
