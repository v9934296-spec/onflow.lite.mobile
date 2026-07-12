import AsyncStorage from "@react-native-async-storage/async-storage";

import { isSessionRecap } from "../sessionRecap/completedSessionStore";
import { userScopedStorageKey } from "../storage/userScopedStorage";
import type { LoadResult, StorageResult } from "../types";
import type { SessionRecap } from "../types/sessionRecap";

export interface PendingSessionCompletion {
  sessionId: string;
  endedAt: string;
  recap: SessionRecap;
}

function keyFor(userId: string): string {
  return userScopedStorageKey(userId, "pendingSessionCompletion");
}

function isPendingSessionCompletion(value: unknown): value is PendingSessionCompletion {
  if (!value || typeof value !== "object") return false;
  const o = value as Record<string, unknown>;
  const sessionId = typeof o.sessionId === "string" ? o.sessionId.trim() : "";
  const endedAt = typeof o.endedAt === "string" ? o.endedAt.trim() : "";
  return (
    Boolean(sessionId) &&
    Boolean(endedAt) &&
    Number.isFinite(Date.parse(endedAt)) &&
    isSessionRecap(o.recap) &&
    o.recap.session_id === sessionId &&
    o.recap.ended_at === endedAt
  );
}

export async function loadPendingSessionCompletion(
  userId: string,
): Promise<LoadResult<PendingSessionCompletion | null>> {
  try {
    const raw = await AsyncStorage.getItem(keyFor(userId));
    if (!raw) return { data: null };
    const parsed: unknown = JSON.parse(raw);
    if (!isPendingSessionCompletion(parsed)) {
      return { data: null, loadError: "Pending session completion has an invalid format" };
    }
    return { data: parsed };
  } catch (error) {
    return {
      data: null,
      loadError: error instanceof Error ? error.message : "Failed to load pending session completion",
    };
  }
}

export async function savePendingSessionCompletion(
  userId: string,
  pending: PendingSessionCompletion,
): Promise<StorageResult> {
  if (!isPendingSessionCompletion(pending)) {
    return { ok: false, error: "Pending session completion is invalid and was not saved" };
  }
  try {
    await AsyncStorage.setItem(keyFor(userId), JSON.stringify(pending));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to journal session completion",
    };
  }
}

export async function clearPendingSessionCompletion(userId: string): Promise<StorageResult> {
  try {
    await AsyncStorage.removeItem(keyFor(userId));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to clear session completion journal",
    };
  }
}
