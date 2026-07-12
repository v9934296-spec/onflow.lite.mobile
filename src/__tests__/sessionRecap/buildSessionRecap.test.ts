import { describe, expect, it } from "vitest";
import { buildSessionRecap } from "../../sessionRecap/buildSessionRecap";
import { buildSessionAttempt } from "../../types/sessionAttempt";
import type { SkateSession } from "../../types/api/session";

const SESSION: SkateSession = {
  id: "sess-1",
  user_id: "user-1",
  spot_label: "Ledges",
  focus_trick: "Kickflip",
  notes: null,
  started_at: "2026-07-11T12:00:00.000Z",
  ended_at: null,
  breakthrough_note: null,
  clip_count: 0,
  attempt_count: 0,
  created_at: "2026-07-11T12:00:00.000Z",
  updated_at: "2026-07-11T12:00:00.000Z",
  deleted_at: null,
};

describe("buildSessionRecap", () => {
  it("aggregates landed and missed attempts for the session", () => {
    const endedAt = "2026-07-11T12:10:00.000Z";
    const attempts = [
      buildSessionAttempt({
        sessionId: "sess-1",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "landed",
      }),
      buildSessionAttempt({
        sessionId: "sess-1",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "missed",
      }),
      buildSessionAttempt({
        sessionId: "sess-2",
        trickId: "heelflip",
        canonicalName: "Heelflip",
        outcome: "landed",
      }),
    ];

    const recap = buildSessionRecap(SESSION, attempts, endedAt);
    expect(recap.attempts_count).toBe(2);
    expect(recap.landed_count).toBe(1);
    expect(recap.missed_count).toBe(1);
    expect(recap.landed_rate).toBe(0.5);
    expect(recap.duration_seconds).toBe(600);
    expect(recap.trick_breakdown).toHaveLength(1);
    expect(recap.trick_breakdown[0]?.canonicalName).toBe("Kickflip");
  });

  it("handles empty sessions honestly", () => {
    const recap = buildSessionRecap(SESSION, [], "2026-07-11T12:05:00.000Z");
    expect(recap.attempts_count).toBe(0);
    expect(recap.landed_rate).toBeNull();
    expect(recap.trick_breakdown).toEqual([]);
  });
});
