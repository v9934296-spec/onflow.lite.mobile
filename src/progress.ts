import AsyncStorage from "@react-native-async-storage/async-storage";
import { LandedAttempt, LoadResult, StorageResult } from "./types";

const KEY = "onflow_lite_progress_v1";

export type DayStatus = "landed" | "bailed" | "none";

export interface DaySlot {
  date: string; // YYYY-MM-DD
  label: string;
  status: DayStatus;
}

function toDateKey(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dayLabel(d: Date): string {
  return d.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
}

export function getLast7Days(attempts: LandedAttempt[], now = new Date()): DaySlot[] {
  const byDate = new Map<string, DayStatus>();

  for (const a of attempts) {
    const key = toDateKey(new Date(a.loggedAt));
    const prev = byDate.get(key);
    const isLanded = a.manualOutcome === "landed" || a.landed;
    const isMissed = a.manualOutcome === "missed";
    if (isLanded) {
      byDate.set(key, "landed");
    } else if (isMissed && prev !== "landed") {
      byDate.set(key, "bailed");
    }
  }

  const slots: DaySlot[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setHours(12, 0, 0, 0);
    d.setDate(d.getDate() - i);
    const date = toDateKey(d);
    slots.push({
      date,
      label: dayLabel(d),
      status: byDate.get(date) ?? "none",
    });
  }
  return slots;
}

/**
 * Gate decision: this streak is a self-reported habit metric, not a progression
 * score. It may be shown for engagement, but must never feed P.T.E. ratings,
 * skill scores, evidence classes, or any claim of measured progression.
 */
export function getTrickStreak(attempts: LandedAttempt[], trick: string, now = new Date()): number {
  const trickAttempts = attempts.filter((a) => a.trick === trick);
  if (trickAttempts.length === 0) return 0;

  const landedDates = new Set<string>();
  for (const a of trickAttempts) {
    if (a.manualOutcome === "landed" || a.landed) landedDates.add(toDateKey(new Date(a.loggedAt)));
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

export function getBestTrickStreak(attempts: LandedAttempt[], now = new Date()): { trick: string; streak: number } | null {
  const tricks = [...new Set(attempts.map((a) => a.trick))];
  let best: { trick: string; streak: number } | null = null;
  for (const trick of tricks) {
    const streak = getTrickStreak(attempts, trick, now);
    if (!best || streak > best.streak) best = { trick, streak };
  }
  return best && best.streak > 0 ? best : null;
}

export async function loadAttempts(): Promise<LoadResult<LandedAttempt[]>> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return { data: [] };
    return { data: JSON.parse(raw) as LandedAttempt[] };
  } catch (e) {
    return { data: [], loadError: e instanceof Error ? e.message : "Failed to load progress" };
  }
}

export async function saveAttempts(attempts: LandedAttempt[]): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(attempts));
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Failed to save progress" };
  }
}

export async function appendAttempt(attempt: LandedAttempt): Promise<StorageResult> {
  const { data } = await loadAttempts();
  return saveAttempts([...data, attempt]);
}

export async function clearAttempts(): Promise<StorageResult> {
  try {
    await AsyncStorage.removeItem(KEY);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Failed to clear progress" };
  }
}
