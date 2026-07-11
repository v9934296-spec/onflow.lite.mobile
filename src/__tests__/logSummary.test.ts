import { describe, expect, it } from "vitest";
import { summarizeLog } from "../logSummary";
import { Analysis, LoggedClip } from "../types";
import { ENGINE_VERSION } from "../engine";

function mockAnalysis(overrides: Partial<Analysis> = {}): Analysis {
  return {
    trickCalled: "Ollie",
    trickOnFilm: null,
    mismatch: false,
    abstained: false,
    rating: null,
    verdict: "test",
    observations: [],
    breakdown: null,
    workOn: "test",
    styleNote: null,
    source: "user",
    engineVersion: ENGINE_VERSION,
    evidenceClass: "ESTIMATE",
    confidence: 25,
    receipts: [],
    abstainReason: null,
    ...overrides,
  };
}

describe("summarizeLog", () => {
  it("computes landed percentage from manual logs", () => {
    const log: LoggedClip[] = [
      {
        id: "1",
        loggedAt: "2026-07-10T00:00:00.000Z",
        analysis: mockAnalysis(),
        manualLog: { manualOutcome: "landed", attempts: 3, spot: "flat", notes: "" },
      },
      {
        id: "2",
        loggedAt: "2026-07-10T01:00:00.000Z",
        analysis: mockAnalysis({ trickCalled: "Kickflip" }),
        manualLog: { manualOutcome: "missed", attempts: 2, spot: "ledge", notes: "" },
      },
    ];
    const s = summarizeLog(log);
    expect(s.totalAttempts).toBe(5);
    expect(s.landedPct).toBe(50);
    expect(s.practicedTricks).toEqual(["Ollie", "Kickflip"]);
  });

  it("tallies evidence classes across clips", () => {
    const log: LoggedClip[] = [
      { id: "1", loggedAt: "", analysis: mockAnalysis({ evidenceClass: "ESTIMATE" }) },
      { id: "2", loggedAt: "", analysis: mockAnalysis({ evidenceClass: "DETECTED", source: "sample" }) },
    ];
    const s = summarizeLog(log);
    expect(s.evidenceTally.ESTIMATE).toBe(1);
    expect(s.evidenceTally.DETECTED).toBe(1);
  });
});
