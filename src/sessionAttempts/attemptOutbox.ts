import AsyncStorage from "@react-native-async-storage/async-storage";
import { syncSessionAttempts } from "../api/attemptApi";
import type { SessionAttempt } from "../types/sessionAttempt";
import { scopedKey } from "../storage/userScope";

const OUTBOX_KEY = "onflow.sessionAttemptOutbox.v1";
const MAX_OUTBOX = 500;

/** Serialize enqueue + flush so load→modify→save cannot lose concurrent updates. */
let outboxGate: Promise<void> = Promise.resolve();

function withOutboxLock<T>(fn: () => Promise<T>): Promise<T> {
  const run = outboxGate.then(fn, fn);
  outboxGate = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
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

async function loadOutbox(): Promise<SessionAttempt[]> {
  try {
    const raw = await AsyncStorage.getItem(scopedKey(OUTBOX_KEY));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isSessionAttempt);
  } catch {
    return [];
  }
}

async function saveOutbox(items: SessionAttempt[]): Promise<void> {
  const trimmed = items.slice(-MAX_OUTBOX);
  await AsyncStorage.setItem(scopedKey(OUTBOX_KEY), JSON.stringify(trimmed));
}

/** Queue an attempt for server sync (idempotent by attempt id). */
export async function enqueueAttemptForSync(attempt: SessionAttempt): Promise<void> {
  await withOutboxLock(async () => {
    const box = await loadOutbox();
    if (box.some((a) => a.id === attempt.id)) return;
    box.push(attempt);
    await saveOutbox(box);
  });
}

/**
 * Flush the offline outbox to ``POST /api/v1/session-attempts/sync``.
 * Removes accepted ids; leaves rejected/failed for retry.
 */
export async function flushAttemptOutbox(): Promise<{
  flushed: number;
  remaining: number;
  error?: string;
}> {
  return withOutboxLock(async () => {
    const box = await loadOutbox();
    if (box.length === 0) return { flushed: 0, remaining: 0 };

    const result = await syncSessionAttempts(box);
    if (!result.ok) {
      return { flushed: 0, remaining: box.length, error: result.error.message };
    }

    // Re-read after network so concurrent enqueues under the lock aren't possible,
    // but ids accepted while we held the lock are still dropped from the latest box.
    const latest = await loadOutbox();
    const accepted = new Set(result.data.accepted);
    // Drop every server-rejected id (including soft validation rejects). Keeping
    // them retries forever and can brick endSession when remaining > 0.
    const rejected = new Set(result.data.rejected.map((r) => r.id));
    const remaining = latest.filter((a) => !accepted.has(a.id) && !rejected.has(a.id));
    await saveOutbox(remaining);
    return { flushed: accepted.size, remaining: remaining.length };
  });
}
