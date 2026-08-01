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

const syncMock = vi.fn();
vi.mock("../../api/attemptApi", () => ({
  syncSessionAttempts: (...args: unknown[]) => syncMock(...args),
}));

vi.mock("../../storage/userScope", () => ({
  scopedKey: (key: string) => `anon:${key}`,
  setStorageUserId: vi.fn(),
  getStorageUserId: vi.fn(() => null),
  activateStorageForUser: vi.fn(),
  migrateLegacyStorageForUser: vi.fn(),
}));

import {
  enqueueAttemptForSync,
  flushAttemptOutbox,
} from "../../sessionAttempts/attemptOutbox";
import { buildSessionAttempt } from "../../types/sessionAttempt";

describe("attemptOutbox lock", () => {
  beforeEach(() => {
    syncMock.mockReset();
  });

  afterEach(async () => {
    syncMock.mockResolvedValue({
      ok: true,
      data: { accepted: [], rejected: [] },
    });
    await flushAttemptOutbox();
  });

  it("does not drop a concurrently enqueued attempt when flush finishes", async () => {
    const a1 = buildSessionAttempt({
      sessionId: "sess-1",
      trickId: "kickflip",
      canonicalName: "Kickflip",
      outcome: "landed",
    });
    const a2 = buildSessionAttempt({
      sessionId: "sess-1",
      trickId: "heelflip",
      canonicalName: "Heelflip",
      outcome: "missed",
    });

    await enqueueAttemptForSync(a1);

    let releaseSync!: () => void;
    const syncGate = new Promise<void>((resolve) => {
      releaseSync = resolve;
    });

    syncMock.mockImplementation(async (attempts: { id: string }[]) => {
      await syncGate;
      return {
        ok: true,
        data: {
          accepted: attempts.map((a) => a.id),
          rejected: [],
        },
      };
    });

    const flushPromise = flushAttemptOutbox();
    // Wait until flush has entered the lock and started the network call.
    await vi.waitFor(() => expect(syncMock).toHaveBeenCalled());

    const enqueuePromise = enqueueAttemptForSync(a2);
    releaseSync();
    await flushPromise;
    await enqueuePromise;

    // Second flush should still see a2 (not wiped by stale save of []).
    syncMock.mockResolvedValueOnce({
      ok: true,
      data: { accepted: [a2.id], rejected: [] },
    });
    const second = await flushAttemptOutbox();
    expect(second.flushed).toBe(1);
    expect(syncMock.mock.calls.at(-1)?.[0]?.map((a: { id: string }) => a.id)).toEqual([
      a2.id,
    ]);
  });
});
