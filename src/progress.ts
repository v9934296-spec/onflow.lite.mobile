import AsyncStorage from "@react-native-async-storage/async-storage";
import { LandedAttempt, LoadResult, StorageResult } from "./types";
import { scopedKey } from "./storage/userScope";

const KEY = "onflow_lite_progress_v1";

export type DayStatus = "landed" | "bailed" | "none";

export interface DaySlot {
  date: string; // YYYY-MM-DD
  label: string;
  status: DayStatus;
}

function toDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dayLabel(date: Date): string {
  return date.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
}

function isUserAttempt(attempt: LandedAttempt): boolean {
  return attempt.source === "user";
}

export function getLast7Days(attempts: LandedAttempt[], now = new Date()): DaySlot[] {
  const byDate = new Map<string, DayStatus>();

  for (const attempt of attempts) {
    if (!isUserAttempt(attempt)) continue;

    const key = toDateKey(new Date(attempt.loggedAt));
    const previous = byDate.get(key);
    const isLanded = attempt.manualOutcome === "landed" || attempt.landed;
    const isMissed = attempt.manualOutcome === "missed";
    if (isLanded) {
      byDate.set(key, "landed");
    } else if (isMissed && previous !== "landed") {
      byDate.set(key, "bailed");
    }
  }

  const slots: DaySlot[] = [];
  for (let daysAgo = 6; daysAgo >= 0; daysAgo--) {
    const date = new Date(now);
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() - daysAgo);
    const dateKey = toDateKey(date);
    slots.push({
      date: dateKey,
      label: dayLabel(date),
      status: byDate.get(dateKey) ?? "none",
    });
  }
  return slots;
}

/**
 * Gate decision: this streak is a self-reported habit metric, not a progression
 * score. It may be shown for engagement, but must never feed P.T.E. ratings,
 * skill scores, evidence classes, or any claim of measured progression.
 */
export function getTrickStreak(
  attempts: LandedAttempt[],
  trick: string,
  now = new Date(),
): number {
  const trickAttempts = attempts.filter(
    (attempt) => isUserAttempt(attempt) && attempt.trick === trick,
  );
  if (trickAttempts.length === 0) return 0;

  const landedDates = new Set<string>();
  for (const attempt of trickAttempts) {
    if (attempt.manualOutcome === "landed" || attempt.landed) {
      landedDates.add(toDateKey(new Date(attempt.loggedAt)));
    }
  }

  let streak = 0;
  const cursor = new Date(now);
  cursor.setHours(12, 0, 0, 0);

  while (true) {
    const key = toDateKey(cursor);
    if (landedDates.has(key)) {
      streak++;
      cursor.setDate(cursor.getDate() - 1);
    } else {
      break;
    }
  }
  return streak;
}

export function getBestTrickStreak(
  attempts: LandedAttempt[],
  now = new Date(),
): { trick: string; streak: number } | null {
  const tricks = [
    ...new Set(attempts.filter(isUserAttempt).map((attempt) => attempt.trick)),
  ];
  let best: { trick: string; streak: number } | null = null;
  for (const trick of tricks) {
    const streak = getTrickStreak(attempts, trick, now);
    if (!best || streak > best.streak) best = { trick, streak };
  }
  return best && best.streak > 0 ? best : null;
}

export async function loadAttempts(): Promise<LoadResult<LandedAttempt[]>> {
  try {
    const raw = await AsyncStorage.getItem(scopedKey(KEY));
    if (!raw) return { data: [] };

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return { data: [], loadError: "Saved progress has an invalid format" };
    }

    return { data: parsed as LandedAttempt[] };
  } catch (error) {
    return {
      data: [],
      loadError: error instanceof Error ? error.message : "Failed to load progress",
    };
  }
}

export async function saveAttempts(attempts: LandedAttempt[]): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(scopedKey(KEY), JSON.stringify(attempts));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to save progress",
    };
  }
}

export async function appendAttempt(attempt: LandedAttempt): Promise<StorageResult> {
  const { data } = await loadAttempts();
  return saveAttempts([...data, attempt]);
}

export async function clearAttempts(): Promise<StorageResult> {
  try {
    await AsyncStorage.removeItem(scopedKey(KEY));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to clear progress",
    };
  }
}
