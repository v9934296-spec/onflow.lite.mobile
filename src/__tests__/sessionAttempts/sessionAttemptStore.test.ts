import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: { version: "1.0.0", ios: { buildNumber: "1" } },
    nativeBuildVersion: "1",
  },
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
  appendSessionAttempt,
  clearSessionAttempts,
  loadSessionAttempts,
} from "../../sessionAttempts/sessionAttemptStore";
import { buildSessionAttempt } from "../../types/sessionAttempt";

describe("sessionAttemptStore", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;

  beforeEach(() => {
    // Unconfigured API → fetch/merge/outbox flush are no-ops for unit tests.
    delete process.env.EXPO_PUBLIC_API_URL;
  });

  afterEach(async () => {
    await clearSessionAttempts("sess-1");
    await clearSessionAttempts("sess-2");
    if (originalUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = originalUrl;
  });

  it("returns empty list for unknown session", async () => {
    const result = await loadSessionAttempts("unknown");
    expect(result.data).toEqual([]);
  });

  it("appends and loads attempts per session", async () => {
    const attempt = buildSessionAttempt({
      sessionId: "sess-1",
      trickId: "kickflip",
      canonicalName: "Kickflip",
      outcome: "landed",
    });

    const save = await appendSessionAttempt(attempt);
    expect(save.ok).toBe(true);

    const loaded = await loadSessionAttempts("sess-1");
    expect(loaded.data).toHaveLength(1);
    expect(loaded.data[0]?.outcome).toBe("landed");
    expect(loaded.data[0]?.trickId).toBe("kickflip");
  });

  it("keeps attempts isolated by session id", async () => {
    await appendSessionAttempt(
      buildSessionAttempt({
        sessionId: "sess-1",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "missed",
      }),
    );
    await appendSessionAttempt(
      buildSessionAttempt({
        sessionId: "sess-2",
        trickId: "heelflip",
        canonicalName: "Heelflip",
        outcome: "landed",
      }),
    );

    expect((await loadSessionAttempts("sess-1")).data).toHaveLength(1);
    expect((await loadSessionAttempts("sess-2")).data[0]?.outcome).toBe("landed");
  });

  it("clears attempts for one session", async () => {
    await appendSessionAttempt(
      buildSessionAttempt({
        sessionId: "sess-1",
        trickId: "kickflip",
        canonicalName: "Kickflip",
        outcome: "landed",
      }),
    );
    await appendSessionAttempt(
      buildSessionAttempt({
        sessionId: "sess-2",
        trickId: "heelflip",
        canonicalName: "Heelflip",
        outcome: "landed",
      }),
    );

    await clearSessionAttempts("sess-1");
    expect((await loadSessionAttempts("sess-1")).data).toEqual([]);
    expect((await loadSessionAttempts("sess-2")).data).toHaveLength(1);
  });
});
