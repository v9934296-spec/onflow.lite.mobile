import { afterEach, describe, expect, it, vi } from "vitest";

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
  loadLastRecapSessionId,
  saveActiveSessionId,
  saveLastRecapSessionId,
} from "../activeSessionStore";

const USER_A = "user-a";
const USER_B = "user-b";

describe("activeSessionStore", () => {
  afterEach(async () => {
    await clearActiveSessionId(USER_A);
    await clearActiveSessionId(USER_B);
  });

  it("returns null when no active session is stored", async () => {
    expect(await loadActiveSessionId(USER_A)).toBeNull();
  });

  it("saves and loads active session id", async () => {
    await saveActiveSessionId(USER_A, "sess-abc");
    expect(await loadActiveSessionId(USER_A)).toBe("sess-abc");
  });

  it("does not expose one user's active session to another", async () => {
    await saveActiveSessionId(USER_A, "sess-abc");
    expect(await loadActiveSessionId(USER_B)).toBeNull();
  });

  it("clears stored session id", async () => {
    await saveActiveSessionId(USER_A, "sess-abc");
    await clearActiveSessionId(USER_A);
    expect(await loadActiveSessionId(USER_A)).toBeNull();
  });

  it("ignores blank session ids", async () => {
    await saveActiveSessionId(USER_A, "   ");
    expect(await loadActiveSessionId(USER_A)).toBeNull();
  });

  it("saves and loads last recap session id", async () => {
    await saveLastRecapSessionId(USER_A, "recap-sess");
    expect(await loadLastRecapSessionId(USER_A)).toBe("recap-sess");
    expect(await loadLastRecapSessionId(USER_B)).toBeNull();
  });
});
