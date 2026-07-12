import { beforeEach, describe, expect, it, vi } from "vitest";

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
  clearPendingSessionCompletion,
  loadPendingSessionCompletion,
  savePendingSessionCompletion,
} from "../../skateSession/sessionCompletionStore";

const PENDING = {
  sessionId: "session-1",
  endedAt: "2026-07-11T12:10:00.000Z",
  recap: {
    session_id: "session-1",
    started_at: "2026-07-11T12:00:00.000Z",
    ended_at: "2026-07-11T12:10:00.000Z",
    duration_seconds: 600,
    spot_label: null,
    focus_trick: "Kickflip",
    attempts_count: 2,
    landed_count: 1,
    missed_count: 1,
    landed_rate: 0.5,
    trick_breakdown: [
      { canonicalName: "Kickflip", attempts: 2, landed: 1, missed: 1 },
    ],
  },
};

describe("sessionCompletionStore", () => {
  beforeEach(() => store.clear());

  it("persists a completion journal before finalization", async () => {
    expect((await savePendingSessionCompletion("user-a", PENDING)).ok).toBe(true);
    expect((await loadPendingSessionCompletion("user-a")).data).toEqual(PENDING);
  });

  it("isolates completion journals by user", async () => {
    await savePendingSessionCompletion("user-a", PENDING);
    expect((await loadPendingSessionCompletion("user-b")).data).toBeNull();
  });

  it("clears the journal after recap persistence succeeds", async () => {
    await savePendingSessionCompletion("user-a", PENDING);
    expect((await clearPendingSessionCompletion("user-a")).ok).toBe(true);
    expect((await loadPendingSessionCompletion("user-a")).data).toBeNull();
  });

  it("rejects malformed completion data", async () => {
    store.set(
      "onflow.user.user-a.pendingSessionCompletion.v1",
      JSON.stringify({ sessionId: "session-1" }),
    );
    const result = await loadPendingSessionCompletion("user-a");
    expect(result.data).toBeNull();
    expect(result.loadError).toBeDefined();
  });
});
