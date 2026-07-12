import { describe, expect, it } from "vitest";
import { formatEventHeadline, formatEventTime } from "../../feed/formatHeadline";
import type { FeedEvent } from "../../types/feedEvent";

const baseEvent: FeedEvent = {
  id: "e1",
  user: {
    user_id: "u1",
    username: "skater",
    tag_name: "Alex",
    profile_photo_url: null,
    tier: "flow",
  },
  event_type: "first_land",
  event_version: "v1",
  generated_at: "2026-07-11T12:00:00Z",
  payload: {
    trick_id: "kickflip",
    trick_display: "Kickflip",
    clip_id: "c1",
    clip_thumbnail_url: "",
    attempt_count_prior: 2,
    pte_rating: 7,
  },
  reactions_summary: {
    fire: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
    saw_it: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
    same_battle: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
    progression: { count: 0, viewer_reacted: false, reactor_user_ids: [] },
  },
};

describe("formatEventHeadline", () => {
  it("formats first land headline", () => {
    expect(formatEventHeadline(baseEvent)).toBe("Alex landed their first kickflip");
  });

  it("formats session recap headline", () => {
    const event: FeedEvent = {
      ...baseEvent,
      event_type: "session_recap",
      payload: {
        session_id: "s1",
        spot_label: "Park ledge",
        clip_count: 2,
        attempt_count: 8,
        tricks_attempted: ["Kickflip"],
        breakthrough_note: null,
        breakthrough_count: 1,
      },
    };
    expect(formatEventHeadline(event)).toContain("Park ledge");
    expect(formatEventHeadline(event)).toContain("8 attempts");
  });
});

describe("formatEventTime", () => {
  it("formats a valid ISO date", () => {
    expect(formatEventTime("2026-07-11T12:00:00Z")).toBeTruthy();
  });

  it("returns empty for invalid dates", () => {
    expect(formatEventTime("not-a-date")).toBe("");
  });
});
