import AsyncStorage from "@react-native-async-storage/async-storage";

import { userScopedStorageKey } from "../storage/userScopedStorage";
import type { LoadResult, StorageResult } from "../types";
import type { SessionRecap } from "../types/sessionRecap";

function keyFor(userId: string): string {
  return userScopedStorageKey(userId, "completedSessions");
}

function isSessionRecap(value: unknown): value is SessionRecap {
  if (!value || typeof value !== "object") return false;
  const o = value as Record<string, unknown>;
  return (
    typeof o.session_id === "string" &&
    typeof o.started_at === "string" &&
    typeof o.ended_at === "string" &&
    typeof o.attempts_count === "number" &&
    typeof o.landed_count === "number" &&
    typeof o.missed_count === "number" &&
    Array.isArray(o.trick_breakdown)
  );
}

async function loadAll(userId: string): Promise<LoadResult<SessionRecap[]>> {
  try {
    const raw = await AsyncStorage.getItem(keyFor(userId));
    if (!raw) return { data: [] };

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return { data: [], loadError: "Saved session history has an invalid format" };
    }

    return { data: parsed.filter(isSessionRecap) };
  } catch (error) {
    return {
      data: [],
      loadError: error instanceof Error ? error.message : "Failed to load session history",
    };
  }
}

async function saveAll(userId: string, recaps: SessionRecap[]): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(keyFor(userId), JSON.stringify(recaps));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to save session history",
    };
  }
}

export async function loadCompletedSessionRecap(
  userId: string,
  sessionId: string,
): Promise<LoadResult<SessionRecap | null>> {
  const sid = sessionId.trim();
  if (!sid) return { data: null };

  const result = await loadAll(userId);
  const recap = result.data.find((r) => r.session_id === sid) ?? null;
  return { data: recap, loadError: result.loadError };
}

export async function saveCompletedSessionRecap(
  userId: string,
  recap: SessionRecap,
): Promise<StorageResult> {
  const result = await loadAll(userId);
  const without = result.data.filter((r) => r.session_id !== recap.session_id);
  const next = [recap, ...without].sort(
    (a, b) => new Date(b.ended_at).getTime() - new Date(a.ended_at).getTime(),
  );
  return saveAll(userId, next);
}

export async function listCompletedSessionRecaps(userId: string): Promise<LoadResult<SessionRecap[]>> {
  const result = await loadAll(userId);
  const sorted = [...result.data].sort(
    (a, b) => new Date(b.ended_at).getTime() - new Date(a.ended_at).getTime(),
  );
  return { data: sorted, loadError: result.loadError };
}
