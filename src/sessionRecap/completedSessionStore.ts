import AsyncStorage from "@react-native-async-storage/async-storage";

import { userScopedStorageKey } from "../storage/userScopedStorage";
import type { LoadResult, StorageResult } from "../types";
import type { SessionRecap, SessionRecapTrickRow } from "../types/sessionRecap";

function keyFor(userId: string): string {
  return userScopedStorageKey(userId, "completedSessions");
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isTimestamp(value: unknown): value is string {
  return isNonEmptyString(value) && Number.isFinite(Date.parse(value));
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isTrickRow(value: unknown): value is SessionRecapTrickRow {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return (
    isNonEmptyString(row.canonicalName) &&
    isCount(row.landed) &&
    isCount(row.missed) &&
    isCount(row.total) &&
    row.landed + row.missed === row.total
  );
}

export function isSessionRecap(value: unknown): value is SessionRecap {
  if (!value || typeof value !== "object") return false;
  const o = value as Record<string, unknown>;
  if (
    !isNonEmptyString(o.session_id) ||
    !isTimestamp(o.started_at) ||
    !isTimestamp(o.ended_at) ||
    !isNullableString(o.spot_label) ||
    !isNullableString(o.focus_trick) ||
    !isCount(o.attempts_count) ||
    !isCount(o.landed_count) ||
    !isCount(o.missed_count) ||
    o.landed_count + o.missed_count !== o.attempts_count ||
    !Array.isArray(o.trick_breakdown) ||
    !o.trick_breakdown.every(isTrickRow)
  ) {
    return false;
  }

  const rows = o.trick_breakdown as SessionRecapTrickRow[];
  const rowTotals = rows.reduce(
    (sum, row) => ({
      total: sum.total + row.total,
      landed: sum.landed + row.landed,
      missed: sum.missed + row.missed,
    }),
    { total: 0, landed: 0, missed: 0 },
  );
  if (
    rowTotals.total !== o.attempts_count ||
    rowTotals.landed !== o.landed_count ||
    rowTotals.missed !== o.missed_count
  ) {
    return false;
  }

  if (Date.parse(o.ended_at) < Date.parse(o.started_at)) return false;
  if (
    o.duration_seconds !== null &&
    !(
      typeof o.duration_seconds === "number" &&
      Number.isFinite(o.duration_seconds) &&
      o.duration_seconds >= 0
    )
  ) {
    return false;
  }
  if (
    o.landed_rate !== null &&
    !(
      typeof o.landed_rate === "number" &&
      Number.isFinite(o.landed_rate) &&
      o.landed_rate >= 0 &&
      o.landed_rate <= 1
    )
  ) {
    return false;
  }
  return true;
}

async function loadAll(userId: string): Promise<LoadResult<SessionRecap[]>> {
  try {
    const raw = await AsyncStorage.getItem(keyFor(userId));
    if (!raw) return { data: [] };

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return { data: [], loadError: "Saved session history has an invalid format" };
    }

    const valid = parsed.filter(isSessionRecap);
    return {
      data: valid,
      loadError:
        valid.length === parsed.length
          ? undefined
          : "Some saved session history entries were invalid and were ignored",
    };
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
  if (!isSessionRecap(recap)) {
    return { ok: false, error: "Session recap is invalid and was not saved" };
  }
  const result = await loadAll(userId);
  const without = result.data.filter((r) => r.session_id !== recap.session_id);
  const next = [recap, ...without].sort(
    (a, b) => Date.parse(b.ended_at) - Date.parse(a.ended_at),
  );
  return saveAll(userId, next);
}

export async function listCompletedSessionRecaps(userId: string): Promise<LoadResult<SessionRecap[]>> {
  const result = await loadAll(userId);
  const sorted = [...result.data].sort(
    (a, b) => Date.parse(b.ended_at) - Date.parse(a.ended_at),
  );
  return { data: sorted, loadError: result.loadError };
}
