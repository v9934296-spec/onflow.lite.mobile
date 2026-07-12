import { describe, expect, it } from "vitest";
import {
  excludeActiveSessionFromHistory,
  formatSessionHistoryDate,
  formatSessionHistorySubtitle,
  formatSessionHistoryTitle,
} from "../../sessionHistory/sessionHistoryFormat";
import type { SessionRecap } from "../../types/sessionRecap";

const BASE_RECAP: SessionRecap = {
  session_id: "sess-1",
  started_at: "2026-07-11T12:00:00.000Z",
  ended_at: "2026-07-11T13:00:00.000Z",
  spot_label: "Fremont",
  focus_trick: "Kickflip",
  attempts_count: 3,
  landed_count: 2,
  missed_count: 1,
  landed_rate: 0.67,
  duration_seconds: 3600,
  trick_breakdown: [{ canonicalName: "Kickflip", landed: 2, missed: 1, total: 3 }],
};

describe("formatSessionHistoryTitle", () => {
  it("prefers spot label over focus trick", () => {
    expect(formatSessionHistoryTitle(BASE_RECAP)).toBe("Fremont");
  });

  it("falls back to focus trick or trick breakdown", () => {
    expect(formatSessionHistoryTitle({ ...BASE_RECAP, spot_label: null })).toBe("Kickflip");
    expect(
      formatSessionHistoryTitle({
        ...BASE_RECAP,
        spot_label: null,
        focus_trick: null,
        trick_breakdown: [],
      }),
    ).toBe("Session");
  });
});

describe("formatSessionHistorySubtitle", () => {
  it("includes date and attempt totals", () => {
    const sub = formatSessionHistorySubtitle(BASE_RECAP);
    expect(sub).toContain("2 landed");
    expect(sub).toContain("1 missed");
    expect(sub).toContain("3 attempts");
  });

  it("handles empty sessions honestly", () => {
    expect(formatSessionHistorySubtitle({ ...BASE_RECAP, attempts_count: 0, landed_count: 0, missed_count: 0 })).toContain(
      "No attempts logged",
    );
  });
});

describe("formatSessionHistoryDate", () => {
  it("labels today and yesterday", () => {
    const now = new Date("2026-07-11T18:00:00.000Z");
    expect(formatSessionHistoryDate("2026-07-11T10:00:00.000Z", now)).toBe("Today");
    expect(formatSessionHistoryDate("2026-07-10T10:00:00.000Z", now)).toBe("Yesterday");
  });
});

describe("excludeActiveSessionFromHistory", () => {
  it("removes the active session id from history rows", () => {
    const rows = [
      BASE_RECAP,
      { ...BASE_RECAP, session_id: "sess-2", spot_label: "Park" },
    ];
    expect(excludeActiveSessionFromHistory(rows, "sess-1")).toHaveLength(1);
    expect(excludeActiveSessionFromHistory(rows, "sess-1")[0]?.session_id).toBe("sess-2");
  });
});
