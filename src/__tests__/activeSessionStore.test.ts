import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@react-native-async-storage/async-storage", () => {
  const store = new Map<string, string>();
  return {
    default: {
      getItem: vi.fn(async (key: string) => store.get(key) ?? null),
      setItem: vi.fn(async (key: string, value: string) => {
        store.set(key, value);
      }),
      removeItem: vi.fn(async (key: string) => {
        store.delete(key);
      }),
      clear: vi.fn(async () => {
        store.clear();
      }),
    },
    __store: store,
  };
});

import {
  clearActiveSessionId,
  loadActiveSessionId,
  saveActiveSessionId,
} from "../activeSessionStore";

describe("activeSessionStore", () => {
  afterEach(async () => {
    await clearActiveSessionId();
  });

  it("returns null when no active session is stored", async () => {
    expect(await loadActiveSessionId()).toBeNull();
  });

  it("saves and loads active session id", async () => {
    await saveActiveSessionId("sess-abc");
    expect(await loadActiveSessionId()).toBe("sess-abc");
  });

  it("clears stored session id", async () => {
    await saveActiveSessionId("sess-abc");
    await clearActiveSessionId();
    expect(await loadActiveSessionId()).toBeNull();
  });

  it("ignores blank session ids", async () => {
    await saveActiveSessionId("   ");
    expect(await loadActiveSessionId()).toBeNull();
  });
});
