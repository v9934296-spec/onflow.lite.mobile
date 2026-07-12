import { describe, expect, it } from "vitest";
import {
  buildSessionAttempt,
  summarizeSessionAttempts,
  type SessionAttempt,
} from "../../types/sessionAttempt";

describe("buildSessionAttempt", () => {
  it("stores trick metadata and outcome", () => {
    const attempt = buildSessionAttempt({
      sessionId: "sess-1",
      trickId: "fakie kickflip",
      canonicalName: "Fakie kickflip",
      outcome: "missed",
    });
    expect(attempt.sessionId).toBe("sess-1");
    expect(attempt.trickId).toBe("fakie kickflip");
    expect(attempt.canonicalName).toBe("Fakie kickflip");
    expect(attempt.outcome).toBe("missed");
    expect(attempt.id).toBeTruthy();
    expect(attempt.loggedAt).toBeTruthy();
  });
});

describe("summarizeSessionAttempts", () => {
  it("counts landed and missed attempts", () => {
    const attempts: SessionAttempt[] = [
      buildSessionAttempt({
        sessionId: "s",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "landed",
      }),
      buildSessionAttempt({
        sessionId: "s",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "landed",
      }),
      buildSessionAttempt({
        sessionId: "s",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "missed",
      }),
    ];
    expect(summarizeSessionAttempts(attempts)).toEqual({
      total: 3,
      landed: 2,
      missed: 1,
    });
  });
});
