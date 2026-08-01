import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const store = new Map<string, string>();

vi.mock("@react-native-async-storage/async-storage", () => ({
  default: {
    getItem: vi.fn(async (key: string) => store.get(key) ?? null),
    setItem: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    removeItem: vi.fn(async (key: string) => {
      store.delete(key);
    }),
  },
}));

import {
  activateStorageForUser,
  getStorageUserId,
  scopedKey,
  setStorageUserId,
} from "../../storage/userScope";
import { clearLog, loadLog, saveLog } from "../../storage/clipLog";
import type { LoggedClip } from "../../types";

function makeEntry(id: string): LoggedClip {
  return {
    id,
    loggedAt: "2026-07-16T00:00:00.000Z",
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
      source: "user",
      engineVersion: "pte-lite-v0.1",
      evidenceClass: "NO EVIDENCE",
      confidence: 0,
      receipts: [],
      abstainReason: "test",
    },
  } as LoggedClip;
}

describe("userScope", () => {
  beforeEach(() => {
    store.clear();
    setStorageUserId(null);
  });

  afterEach(() => {
    setStorageUserId(null);
  });

  it("returns the base key when no user is set", () => {
    expect(scopedKey("onflow_lite_log_v1")).toBe("onflow_lite_log_v1");
    expect(getStorageUserId()).toBeNull();
  });

  it("namespaces the key once a user is set", () => {
    setStorageUserId("user-a");
    expect(scopedKey("onflow_lite_log_v1")).toBe("u:user-a:onflow_lite_log_v1");
    expect(getStorageUserId()).toBe("user-a");
  });

  it("treats blank/whitespace user ids as no user", () => {
    setStorageUserId("   ");
    expect(getStorageUserId()).toBeNull();
    expect(scopedKey("k")).toBe("k");
  });

  it("isolates one account's log from another on the same device", async () => {
    await saveLog("user-a", [makeEntry("a1")]);
    expect((await loadLog("user-b")).data).toEqual([]);
    await saveLog("user-b", [makeEntry("b1")]);

    const aData = (await loadLog("user-a")).data;
    expect(aData).toHaveLength(1);
    expect(aData[0]?.id).toBe("a1");

    const bData = (await loadLog("user-b")).data;
    expect(bData).toHaveLength(1);
    expect(bData[0]?.id).toBe("b1");
  });

  it("clearing one account's log does not touch another's", async () => {
    await saveLog("user-a", [makeEntry("a1")]);
    await saveLog("user-b", [makeEntry("b1")]);

    await clearLog("user-a");
    expect((await loadLog("user-a")).data).toEqual([]);
    expect((await loadLog("user-b")).data).toHaveLength(1);
  });

  it("migrates legacy unscoped data into the first authenticated user once", async () => {
    store.set("onflow_lite_log_v1", JSON.stringify([makeEntry("legacy")]));

    await activateStorageForUser("user-a");

    expect(store.has("onflow_lite_log_v1")).toBe(false);
    expect(store.get("u:user-a:onflow_lite_log_v1")).toContain("legacy");
  });

  it("does not give a later account the migrated legacy data", async () => {
    store.set("onflow_lite_log_v1", JSON.stringify([makeEntry("legacy")]));

    await activateStorageForUser("user-a");
    await activateStorageForUser("user-b");

    expect(store.get("u:user-a:onflow_lite_log_v1")).toContain("legacy");
    expect(store.has("u:user-b:onflow_lite_log_v1")).toBe(false);
  });
});
