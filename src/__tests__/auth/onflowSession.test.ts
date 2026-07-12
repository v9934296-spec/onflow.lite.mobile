import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async () => null),
  setItemAsync: vi.fn(async () => undefined),
  deleteItemAsync: vi.fn(async () => undefined),
}));

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
  clearOnflowSession,
  loadOnflowSession,
  resetSessionMigration,
  saveOnflowSession,
} from "../../auth/onflowSession";

describe("onflowSession", () => {
  beforeEach(() => {
    resetSessionMigration();
  });

  afterEach(async () => {
    await clearOnflowSession();
    resetSessionMigration();
  });

  it("returns null when no session is stored", async () => {
    expect(await loadOnflowSession()).toBeNull();
  });

  it("round-trips session storage", async () => {
    await saveOnflowSession({
      token: "tok-abc",
      userId: "user-1",
      email: "skater@example.com",
    });
    expect(await loadOnflowSession()).toEqual({
      token: "tok-abc",
      userId: "user-1",
      email: "skater@example.com",
    });
  });

  it("clears stored session", async () => {
    await saveOnflowSession({ token: "t", userId: "u", email: "e@x.com" });
    await clearOnflowSession();
    expect(await loadOnflowSession()).toBeNull();
  });

  it("returns null when token or user id is missing", async () => {
    await saveOnflowSession({ token: " ", userId: "u", email: "e@x.com" });
    expect(await loadOnflowSession()).toBeNull();
  });
});
