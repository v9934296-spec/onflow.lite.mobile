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
import { clearLog, loadLog, saveLog } from "../../storage";
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
    setStorageUserId("user-a");
    await saveLog([makeEntry("a1")]);

    setStorageUserId("user-b");
    expect((await loadLog()).data).toEqual([]);
    await saveLog([makeEntry("b1")]);

    setStorageUserId("user-a");
    const aData = (await loadLog()).data;
    expect(aData).toHaveLength(1);
    expect(aData[0]?.id).toBe("a1");

    setStorageUserId("user-b");
    const bData = (await loadLog()).data;
    expect(bData).toHaveLength(1);
    expect(bData[0]?.id).toBe("b1");
  });

  it("clearing one account's log does not touch another's", async () => {
    setStorageUserId("user-a");
    await saveLog([makeEntry("a1")]);
    setStorageUserId("user-b");
    await saveLog([makeEntry("b1")]);

    setStorageUserId("user-a");
    await clearLog();
    expect((await loadLog()).data).toEqual([]);

    setStorageUserId("user-b");
    expect((await loadLog()).data).toHaveLength(1);
  });

  it("migrates legacy unscoped data into the first authenticated user once", async () => {
    store.set("onflow_lite_log_v1", JSON.stringify([makeEntry("legacy")]));

    await activateStorageForUser("user-a");

    expect(store.has("onflow_lite_log_v1")).toBe(false);
    const aData = (await loadLog()).data;
    expect(aData).toHaveLength(1);
    expect(aData[0]?.id).toBe("legacy");
  });

  it("does not give a later account the migrated legacy data", async () => {
    store.set("onflow_lite_log_v1", JSON.stringify([makeEntry("legacy")]));

    await activateStorageForUser("user-a");
    await activateStorageForUser("user-b");

    setStorageUserId("user-b");
    expect((await loadLog()).data).toEqual([]);

    setStorageUserId("user-a");
    expect((await loadLog()).data).toHaveLength(1);
  });
});
