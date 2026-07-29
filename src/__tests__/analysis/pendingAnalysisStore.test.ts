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
  clearPendingAnalysisJob,
  loadPendingAnalysisJob,
  savePendingAnalysisJob,
} from "../../analysis/pendingAnalysisStore";

const JOB = {
  jobId: "job-1",
  sessionId: "session-1",
  trickName: "Kickflip",
  selectedTrick: {
    trickId: "kickflip",
    baseTrick: "Kickflip",
    modifiers: [],
    canonicalName: "Kickflip",
  },
  submittedAt: "2026-07-11T12:00:00.000Z",
};

describe("pendingAnalysisStore", () => {
  beforeEach(() => store.clear());

  it("restores a pending job after a simulated restart", async () => {
    expect((await savePendingAnalysisJob("user-a", JOB)).ok).toBe(true);
    expect((await loadPendingAnalysisJob("user-a")).data).toEqual(JOB);
  });

  it("does not expose a pending job to another user", async () => {
    await savePendingAnalysisJob("user-a", JOB);
    expect((await loadPendingAnalysisJob("user-b")).data).toBeNull();
  });

  it("clears a completed or failed job", async () => {
    await savePendingAnalysisJob("user-a", JOB);
    expect((await clearPendingAnalysisJob("user-a")).ok).toBe(true);
    expect((await loadPendingAnalysisJob("user-a")).data).toBeNull();
  });

  it("rejects malformed stored data", async () => {
    store.set("onflow.user.user-a.pendingAnalysis.v1", JSON.stringify({ jobId: "job-1" }));
    const result = await loadPendingAnalysisJob("user-a");
    expect(result.data).toBeNull();
    expect(result.loadError).toBeDefined();
  });
});
