import AsyncStorage from "@react-native-async-storage/async-storage";

import { fetchSessionAttempts } from "../api/attemptApi";
import { userScopedStorageKey } from "../storage/userScopedStorage";
import type { LoadResult, StorageResult } from "../types";
import type { SessionAttempt } from "../types/sessionAttempt";
import { enqueueAttemptForSync, flushAttemptOutbox } from "./attemptOutbox";

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

function mergeById(local: SessionAttempt[], remote: SessionAttempt[]): SessionAttempt[] {
  const map = new Map<string, SessionAttempt>();
  for (const a of remote) map.set(a.id, a);
  for (const a of local) map.set(a.id, a); // local wins on conflict
  return Array.from(map.values()).sort((a, b) => a.loggedAt.localeCompare(b.loggedAt));
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
  let data = result.data[sid] ?? [];

  // Best-effort merge from server (device reinstall / multi-device).
  try {
    const remote = await fetchSessionAttempts(sid);
    if (remote.ok && remote.data.length > 0) {
      data = mergeById(data, remote.data);
      const store = { ...result.data, [sid]: data };
      await saveStore(userId, store);
    }
  } catch {
    // offline — keep local
  }

  // Drain any pending outbox while we're online.
  void flushAttemptOutbox();

  return {
    data,
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
  const existing = result.data[sid] ?? [];
  if (existing.some((a) => a.id === attempt.id)) {
    await enqueueAttemptForSync(attempt);
    void flushAttemptOutbox();
    return { ok: true };
  }
  const next = [...existing, attempt];
  const saved = await saveStore(userId, { ...result.data, [sid]: next });
  if (!saved.ok) return saved;

  await enqueueAttemptForSync(attempt);
  void flushAttemptOutbox();
  return { ok: true };
}

export async function clearSessionAttempts(userId: string, sessionId: string): Promise<StorageResult> {
  const sid = sessionId.trim();
  if (!sid) return { ok: true };

  const result = await loadStore(userId);
  if (!result.data[sid]) return { ok: true };

  const { [sid]: _removed, ...rest } = result.data;
  return saveStore(userId, rest);
}
