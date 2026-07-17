import AsyncStorage from "@react-native-async-storage/async-storage";
import type { LoadResult, StorageResult } from "../types";
import type { SessionAttempt } from "../types/sessionAttempt";
import { scopedKey } from "../storage/userScope";

const KEY = "onflow.sessionAttempts.v1";

type AttemptStore = Record<string, SessionAttempt[]>;

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

async function loadStore(): Promise<LoadResult<AttemptStore>> {
  try {
    const raw = await AsyncStorage.getItem(scopedKey(KEY));
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

async function saveStore(store: AttemptStore): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(scopedKey(KEY), JSON.stringify(store));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to save session attempts",
    };
  }
}

export async function loadSessionAttempts(sessionId: string): Promise<LoadResult<SessionAttempt[]>> {
  const sid = sessionId.trim();
  if (!sid) return { data: [] };

  const result = await loadStore();
  return {
    data: result.data[sid] ?? [],
    loadError: result.loadError,
  };
}

export async function appendSessionAttempt(attempt: SessionAttempt): Promise<StorageResult> {
  const sid = attempt.sessionId.trim();
  if (!sid) return { ok: false, error: "Missing session id" };

  const result = await loadStore();
  const next = [...(result.data[sid] ?? []), attempt];
  return saveStore({ ...result.data, [sid]: next });
}

export async function clearSessionAttempts(sessionId: string): Promise<StorageResult> {
  const sid = sessionId.trim();
  if (!sid) return { ok: true };

  const result = await loadStore();
  if (!result.data[sid]) return { ok: true };

  const { [sid]: _removed, ...rest } = result.data;
  return saveStore(rest);
}
