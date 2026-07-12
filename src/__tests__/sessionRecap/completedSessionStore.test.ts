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
    clear: vi.fn(async () => {
      store.clear();
    }),
  },
}));

import { buildSessionRecap } from "../../sessionRecap/buildSessionRecap";
import {
  loadCompletedSessionRecap,
  listCompletedSessionRecaps,
  saveCompletedSessionRecap,
} from "../../sessionRecap/completedSessionStore";
import type { SkateSession } from "../../types/api/session";

const USER_A = "user-1";
const USER_B = "user-2";
const SESSION: SkateSession = {
  id: "sess-load",
  user_id: USER_A,
  spot_label: null,
  focus_trick: null,
  notes: null,
  started_at: "2026-07-11T12:00:00.000Z",
  ended_at: "2026-07-11T12:05:00.000Z",
  breakthrough_note: null,
  clip_count: 0,
  attempt_count: 0,
  created_at: "2026-07-11T12:00:00.000Z",
  updated_at: "2026-07-11T12:05:00.000Z",
  deleted_at: null,
};

describe("completedSessionStore", () => {
  beforeEach(() => store.clear());

  it("saves and loads a recap by user and session id", async () => {
    const recap = buildSessionRecap(SESSION, [], SESSION.ended_at!);
    expect((await saveCompletedSessionRecap(USER_A, recap)).ok).toBe(true);

    const loaded = await loadCompletedSessionRecap(USER_A, "sess-load");
    expect(loaded.data?.session_id).toBe("sess-load");
    expect(loaded.data?.attempts_count).toBe(0);
    expect((await loadCompletedSessionRecap(USER_B, "sess-load")).data).toBeNull();
  });

  it("lists recaps newest ended first", async () => {
    const older = buildSessionRecap(
      { ...SESSION, id: "sess-old" },
      [],
      "2026-07-10T12:00:00.000Z",
    );
    const newer = buildSessionRecap(
      { ...SESSION, id: "sess-new" },
      [],
      "2026-07-12T12:00:00.000Z",
    );
    await saveCompletedSessionRecap(USER_A, older);
    await saveCompletedSessionRecap(USER_A, newer);

    const listed = await listCompletedSessionRecaps(USER_A);
    expect(listed.data[0]?.session_id).toBe("sess-new");
    expect((await listCompletedSessionRecaps(USER_B)).data).toEqual([]);
  });

  it("refuses to save inconsistent recap totals", async () => {
    const recap = buildSessionRecap(SESSION, [], SESSION.ended_at!);
    const invalid = { ...recap, attempts_count: 1 };
    const result = await saveCompletedSessionRecap(USER_A, invalid);
    expect(result.ok).toBe(false);
    expect(store.size).toBe(0);
  });

  it("ignores corrupted persisted entries and returns a warning", async () => {
    const valid = buildSessionRecap(SESSION, [], SESSION.ended_at!);
    const invalid = { ...valid, landed_count: 2, attempts_count: 0 };
    store.set(
      "onflow.user.user-1.completedSessions.v1",
      JSON.stringify([valid, invalid]),
    );

    const listed = await listCompletedSessionRecaps(USER_A);
    expect(listed.data).toEqual([valid]);
    expect(listed.loadError).toContain("invalid");
  });

  it("rejects recaps whose end time precedes start time", async () => {
    const recap = buildSessionRecap(SESSION, [], SESSION.ended_at!);
    const invalid = {
      ...recap,
      ended_at: "2026-07-11T11:59:00.000Z",
    };
    const result = await saveCompletedSessionRecap(USER_A, invalid);
    expect(result.ok).toBe(false);
  });
});
