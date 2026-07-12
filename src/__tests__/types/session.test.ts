import { describe, expect, it } from "vitest";

import { isSkateSessionActive } from "../../types/api/session";
import type { SkateSession } from "../../types/api/session";

const base: SkateSession = {
  id: "s1",
  user_id: "u1",
  spot_label: null,
  focus_trick: null,
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

describe("isSkateSessionActive", () => {
  it("returns true for open sessions", () => {
    expect(isSkateSessionActive(base)).toBe(true);
  });

  it("returns false when ended_at is set", () => {
    expect(isSkateSessionActive({ ...base, ended_at: "2026-07-11T13:00:00Z" })).toBe(false);
  });

  it("returns false when deleted_at is set", () => {
    expect(isSkateSessionActive({ ...base, deleted_at: "2026-07-11T13:00:00Z" })).toBe(false);
  });

  it("returns false for null", () => {
    expect(isSkateSessionActive(null)).toBe(false);
  });
});
