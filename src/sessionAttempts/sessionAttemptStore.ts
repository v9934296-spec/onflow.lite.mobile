import AsyncStorage from "@react-native-async-storage/async-storage";

import { userScopedStorageKey } from "../storage/userScopedStorage";
import type { LoadResult, StorageResult } from "../types";
import type { SessionAttempt } from "../types/sessionAttempt";

type AttemptStore = Record<string, SessionAttempt[]>;

function keyFor(userId: string): string {
  return userScopedStorageKey(userId, "sessionAttempts");
}

function isSessionAttempt(value: unknown): value is SessionAttempt {
  if (!value || typeof value !== "object") return false;
  const o = value as Record<string, unknown>;
  return (
    typeof o.id === "string" &&
    typeof o.sessionId === "string" &&
    typeof o.trickId === "string" &&
    typeof o.canonicalName === "string" &&
    (o.outcome === "landed" || o.outcome === "missed") &&
    typeof o.loggedAt === "string"
  );
}

async function loadStore(userId: string): Promise<LoadResult<AttemptStore>> {
  try {
    const raw = await AsyncStorage.getItem(keyFor(userId));
    if (!raw) return { data: {} };

    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { data: {}, loadError: "Saved session attempts have an invalid format" };
    }

    const store: AttemptStore = {};
    for (const [sessionId, attempts] of Object.entries(parsed as Record<string, unknown>)) {
      if (!Array.isArray(attempts)) continue;
      const valid = attempts.filter(isSessionAttempt);
      if (valid.length > 0) store[sessionId] = valid;
    }
    return { data: store };
  } catch (error) {
    return {
      data: {},
      loadError: error instanceof Error ? error.message : "Failed to load session attempts",
    };
  }
}

async function saveStore(userId: string, store: AttemptStore): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(keyFor(userId), JSON.stringify(store));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to save session attempts",
    };
  }
}

export async function loadSessionAttempts(
  userId: string,
  sessionId: string,
): Promise<LoadResult<SessionAttempt[]>> {
  const sid = sessionId.trim();
  if (!sid) return { data: [] };

  const result = await loadStore(userId);
  return {
    data: result.data[sid] ?? [],
    loadError: result.loadError,
  };
}

export async function appendSessionAttempt(
  userId: string,
  attempt: SessionAttempt,
): Promise<StorageResult> {
  const sid = attempt.sessionId.trim();
  if (!sid) return { ok: false, error: "Missing session id" };

  const result = await loadStore(userId);
  const next = [...(result.data[sid] ?? []), attempt];
  return saveStore(userId, { ...result.data, [sid]: next });
}

export async function clearSessionAttempts(userId: string, sessionId: string): Promise<StorageResult> {
  const sid = sessionId.trim();
  if (!sid) return { ok: true };

  const result = await loadStore(userId);
  if (!result.data[sid]) return { ok: true };

  const { [sid]: _removed, ...rest } = result.data;
  return saveStore(userId, rest);
}
