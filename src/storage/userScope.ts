import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Per-user isolation for on-device storage.
 *
 * Local stores historically wrote to global AsyncStorage keys, so on a shared
 * device a second account could read the first account's session log, attempts,
 * recaps, and progress. Once the signed-in user is known we namespace every
 * per-user key by user id so accounts can never see each other's local data.
 *
 * Auth/session identity keys (token, user id, email) are intentionally NOT
 * scoped here — they define who the user is and are handled by secureStorage.
 */

let currentUserId: string | null = null;

/**
 * Base keys holding per-user data. Kept in sync with the individual stores so a
 * one-time device migration can move legacy (unscoped) values into the first
 * authenticated user's namespace.
 */
export const SCOPED_BASE_KEYS = [
  "onflow_lite_log_v1",
  "onflow_lite_progress_v1",
  "onflow.sessionAttempts.v1",
  "onflow.completedSessions.v1",
  "onflow.activeSession.v2",
  "onflow.lastRecapSession.v2",
] as const;

const MIGRATION_FLAG_KEY = "onflow.storageScopeMigrated.v1";

function scopePrefix(userId: string): string {
  return `u:${userId}:`;
}

/** Set the active storage user. Pass null on sign-out to stop scoped access. */
export function setStorageUserId(userId: string | null): void {
  const trimmed = userId?.trim();
  currentUserId = trimmed ? trimmed : null;
}

export function getStorageUserId(): string | null {
  return currentUserId;
}

/**
 * Resolve the storage key for the current user. When no user is set (tests,
 * signed-out) the base key is returned so existing behavior is preserved.
 */
export function scopedKey(baseKey: string): string {
  return currentUserId ? `${scopePrefix(currentUserId)}${baseKey}` : baseKey;
}

/**
 * One-time device migration: move legacy unscoped values into `userId`'s
 * namespace, then remove the legacy keys. Runs at most once per device so a
 * later account cannot inherit the first account's migrated data.
 */
export async function migrateLegacyStorageForUser(userId: string): Promise<void> {
  const uid = userId.trim();
  if (!uid) return;

  const alreadyMigrated = await AsyncStorage.getItem(MIGRATION_FLAG_KEY);
  if (alreadyMigrated) return;

  for (const base of SCOPED_BASE_KEYS) {
    const legacy = await AsyncStorage.getItem(base);
    if (legacy == null) continue;

    const target = `${scopePrefix(uid)}${base}`;
    const existing = await AsyncStorage.getItem(target);
    if (existing == null) {
      await AsyncStorage.setItem(target, legacy);
    }
    await AsyncStorage.removeItem(base);
  }

  await AsyncStorage.setItem(MIGRATION_FLAG_KEY, new Date().toISOString());
}

/** Migrate (once) then activate scoped storage for the authenticated user. */
export async function activateStorageForUser(userId: string): Promise<void> {
  await migrateLegacyStorageForUser(userId);
  setStorageUserId(userId);
}
