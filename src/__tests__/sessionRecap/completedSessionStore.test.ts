import { describe, expect, it, vi } from "vitest";

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

import { buildSessionRecap } from "../../sessionRecap/buildSessionRecap";
import {
  loadCompletedSessionRecap,
  listCompletedSessionRecaps,
  saveCompletedSessionRecap,
} from "../../sessionRecap/completedSessionStore";
import type { SkateSession } from "../../types/api/session";

const SESSION: SkateSession = {
  id: "sess-load",
  user_id: "user-1",
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
  it("saves and loads a recap by session id", async () => {
    const recap = buildSessionRecap(SESSION, [], SESSION.ended_at!);
    const save = await saveCompletedSessionRecap(recap);
    expect(save.ok).toBe(true);

    const loaded = await loadCompletedSessionRecap("sess-load");
    expect(loaded.data?.session_id).toBe("sess-load");
    expect(loaded.data?.attempts_count).toBe(0);
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
    await saveCompletedSessionRecap(older);
    await saveCompletedSessionRecap(newer);

    const listed = await listCompletedSessionRecaps();
    expect(listed.data[0]?.session_id).toBe("sess-new");
  });
});
