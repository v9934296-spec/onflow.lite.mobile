import { describe, expect, it } from "vitest";
import { getBestTrickStreak, getLast7Days, getTrickStreak } from "../progress";
import { LandedAttempt } from "../types";

const now = new Date("2026-07-10T12:00:00.000Z");

function attempt(
  trick: string,
  manualOutcome: LandedAttempt["manualOutcome"],
  date: string,
): LandedAttempt {
  return {
    id: `${date}-${trick}`,
    trick,
    manualOutcome,
    attempts: 1,
    spot: "",
    notes: "",
    landed: manualOutcome === "landed",
    loggedAt: `${date}T18:00:00.000Z`,
    source: "user",
  };
}

describe("getLast7Days", () => {
  it("returns 7 day slots ending today", () => {
    const slots = getLast7Days([], now);
    expect(slots).toHaveLength(7);
    expect(slots[6].date).toBe("2026-07-10");
  });

  it("marks landed when any attempt landed that day", () => {
    const attempts = [attempt("Kickflip", "landed", "2026-07-10"), attempt("Kickflip", "missed", "2026-07-10")];
    const slots = getLast7Days(attempts, now);
    expect(slots[6].status).toBe("landed");
  });

  it("marks bailed when only missed attempts exist", () => {
    const attempts = [attempt("Kickflip", "missed", "2026-07-09")];
    const slots = getLast7Days(attempts, now);
    expect(slots[5].status).toBe("bailed");
  });
});

describe("getTrickStreak", () => {
  it("counts consecutive landed days for a trick from today backward", () => {
    const attempts = [
      attempt("Kickflip", "landed", "2026-07-10"),
      attempt("Kickflip", "landed", "2026-07-09"),
      attempt("Kickflip", "missed", "2026-07-08"),
    ];
    expect(getTrickStreak(attempts, "Kickflip", now)).toBe(2);
  });
});

describe("getBestTrickStreak", () => {
  it("returns the trick with the longest active streak", () => {
    const attempts = [
      attempt("Kickflip", "landed", "2026-07-10"),
      attempt("Ollie", "landed", "2026-07-10"),
      attempt("Ollie", "landed", "2026-07-09"),
    ];
    expect(getBestTrickStreak(attempts, now)).toEqual({ trick: "Ollie", streak: 2 });
  });
});
