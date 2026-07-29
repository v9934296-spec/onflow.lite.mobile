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
import { userScopedStorageKey } from "../storage/userScopedStorage";

const USER_A = "user-a";
const USER_B = "user-b";

describe("storage", () => {
  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k]);
  });

  it("loads empty log when nothing saved", async () => {
    const result = await loadLog(USER_A);
    expect(result.data).toEqual([]);
    expect(result.loadError).toBeUndefined();
  });

  it("round-trips log entries without exposing them to another user", async () => {
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
        confidence: null,
        receipts: [],
        abstainReason: "test",
      },
    };
    const saveResult = await saveLog(USER_A, [entry]);
    expect(saveResult.ok).toBe(true);
    expect((await loadLog(USER_A)).data).toHaveLength(1);
    expect((await loadLog(USER_B)).data).toEqual([]);
  });

  it("returns loadError on corrupt JSON", async () => {
    store[userScopedStorageKey(USER_A, "clipLog")] = "{not json";
    const result = await loadLog(USER_A);
    expect(result.data).toEqual([]);
    expect(result.loadError).toBeDefined();
  });

  it("clearLog removes only the selected user's data", async () => {
    await saveLog(USER_A, []);
    await saveLog(USER_B, []);
    const cleared = await clearLog(USER_A);
    expect(cleared.ok).toBe(true);
    expect(await loadLog(USER_A)).toEqual({ data: [] });
    expect(Object.keys(store)).toContain(userScopedStorageKey(USER_B, "clipLog"));
  });
});
