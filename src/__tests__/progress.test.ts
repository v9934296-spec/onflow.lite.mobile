import { describe, expect, it } from "vitest";
import { getBestTrickStreak, getLast7Days, getTrickStreak } from "../progress";
import { LandedAttempt } from "../types";

process.env.TZ = "America/Los_Angeles";

const now = new Date("2026-07-10T19:00:00.000Z");

function attempt(
  trick: string,
  manualOutcome: LandedAttempt["manualOutcome"],
  date: string,
  source: LandedAttempt["source"] = "user",
): LandedAttempt {
  return {
    id: `${date}-${trick}-${source}`,
    trick,
    manualOutcome,
    attempts: 1,
    spot: "",
    notes: "",
    landed: manualOutcome === "landed",
    loggedAt: `${date}T18:00:00.000-07:00`,
    source,
  };
}

describe("getLast7Days", () => {
  it("returns 7 local-day slots ending today", () => {
    const slots = getLast7Days([], now);
    expect(slots).toHaveLength(7);
    expect(slots[6].date).toBe("2026-07-10");
  });

  it("keeps an 8pm Pacific attempt in the local day bucket", () => {
    const eveningAttempt: LandedAttempt = {
      ...attempt("Kickflip", "landed", "2026-07-10"),
      loggedAt: "2026-07-11T03:00:00.000Z",
    };

    const slots = getLast7Days([eveningAttempt], new Date("2026-07-11T06:00:00.000Z"));
    expect(slots[6].date).toBe("2026-07-10");
    expect(slots[6].status).toBe("landed");
  });

  it("marks landed when any attempt landed that day", () => {
    const attempts = [
      attempt("Kickflip", "landed", "2026-07-10"),
      attempt("Kickflip", "missed", "2026-07-10"),
    ];
    const slots = getLast7Days(attempts, now);
    expect(slots[6].status).toBe("landed");
  });

  it("marks bailed when only missed attempts exist", () => {
    const attempts = [attempt("Kickflip", "missed", "2026-07-09")];
    const slots = getLast7Days(attempts, now);
    expect(slots[5].status).toBe("bailed");
  });

  it("ignores scripted sample attempts", () => {
    const slots = getLast7Days([attempt("Kickflip", "landed", "2026-07-10", "sample")], now);
    expect(slots[6].status).toBe("none");
  });
});

describe("getTrickStreak", () => {
  it("counts consecutive landed local days for a trick from today backward", () => {
    const attempts = [
      attempt("Kickflip", "landed", "2026-07-10"),
      attempt("Kickflip", "landed", "2026-07-09"),
      attempt("Kickflip", "missed", "2026-07-08"),
    ];
    expect(getTrickStreak(attempts, "Kickflip", now)).toBe(2);
  });

  it("does not advance the streak day for an evening Pacific landing", () => {
    const attempts: LandedAttempt[] = [
      {
        ...attempt("Kickflip", "landed", "2026-07-10"),
        loggedAt: "2026-07-11T03:00:00.000Z",
      },
      attempt("Kickflip", "landed", "2026-07-09"),
    ];

    expect(getTrickStreak(attempts, "Kickflip", new Date("2026-07-11T06:00:00.000Z"))).toBe(2);
  });

  it("does not count scripted samples toward a self-reported streak", () => {
    expect(
      getTrickStreak([attempt("Kickflip", "landed", "2026-07-10", "sample")], "Kickflip", now),
    ).toBe(0);
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

  it("returns null when only scripted sample attempts exist", () => {
    expect(getBestTrickStreak([attempt("Kickflip", "landed", "2026-07-10", "sample")], now)).toBeNull();
  });
});
