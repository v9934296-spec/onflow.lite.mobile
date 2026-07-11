import { beforeEach, describe, expect, it, vi } from "vitest";

const store: Record<string, string> = {};

vi.mock("@react-native-async-storage/async-storage", () => ({
  default: {
    getItem: vi.fn(async (key: string) => store[key] ?? null),
    setItem: vi.fn(async (key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn(async (key: string) => {
      delete store[key];
    }),
  },
}));

import { clearLog, loadLog, saveLog } from "../storage";

describe("storage", () => {
  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k]);
  });

  it("loads empty log when nothing saved", async () => {
    const result = await loadLog();
    expect(result.data).toEqual([]);
    expect(result.loadError).toBeUndefined();
  });

  it("round-trips log entries", async () => {
    const entry = {
      id: "1",
      loggedAt: "2026-07-10T00:00:00.000Z",
      analysis: {
        trickCalled: "Ollie",
        trickOnFilm: null,
        mismatch: false,
        abstained: true,
        rating: null,
        verdict: "test",
        observations: [],
        breakdown: null,
        workOn: "test",
        styleNote: null,
        source: "user" as const,
        engineVersion: "pte-lite-v0.1",
        evidenceClass: "NO EVIDENCE" as const,
        confidence: 0,
        receipts: [],
        abstainReason: "test",
      },
    };
    const saveResult = await saveLog([entry]);
    expect(saveResult.ok).toBe(true);
    const loadResult = await loadLog();
    expect(loadResult.data).toHaveLength(1);
  });

  it("returns loadError on corrupt JSON", async () => {
    store["onflow_lite_log_v1"] = "{not json";
    const result = await loadLog();
    expect(result.data).toEqual([]);
    expect(result.loadError).toBeDefined();
  });

  it("clearLog removes stored data", async () => {
    await saveLog([]);
    const cleared = await clearLog();
    expect(cleared.ok).toBe(true);
    const result = await loadLog();
    expect(result.data).toEqual([]);
  });
});
