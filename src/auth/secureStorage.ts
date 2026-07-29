/**
 * Encrypted-at-rest key/value storage for auth credentials.
 * AsyncStorage is used only by automated tests where the native SecureStore
 * module is unavailable. Production code fails closed instead of silently
 * downgrading credentials to unencrypted storage.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const USE_ASYNC_TEST_FALLBACK =
  typeof process !== "undefined" &&
  (Boolean(process.env.JEST_WORKER_ID) || process.env.NODE_ENV === "test");

export type SecureStorageOperation = "read" | "write" | "delete" | "migrate";

export class SecureStorageError extends Error {
  readonly operation: SecureStorageOperation;
  readonly key: string;

  constructor(operation: SecureStorageOperation, key: string, cause?: unknown) {
    const causeMessage = cause instanceof Error && cause.message ? `: ${cause.message}` : "";
    super(`Secure credential storage ${operation} failed${causeMessage}`);
    this.name = "SecureStorageError";
    this.operation = operation;
    this.key = key;
  }
}

export async function getSecureItem(key: string): Promise<string | null> {
  if (USE_ASYNC_TEST_FALLBACK) {
    return AsyncStorage.getItem(key);
  }
  try {
    return await SecureStore.getItemAsync(key);
  } catch (error) {
    throw new SecureStorageError("read", key, error);
  }
}

export async function setSecureItem(key: string, value: string): Promise<void> {
  if (USE_ASYNC_TEST_FALLBACK) {
    await AsyncStorage.setItem(key, value);
    return;
  }
  try {
    await SecureStore.setItemAsync(key, value);
  } catch (error) {
    throw new SecureStorageError("write", key, error);
  }
}

export async function removeSecureItem(key: string): Promise<void> {
  if (USE_ASYNC_TEST_FALLBACK) {
    await AsyncStorage.removeItem(key);
    return;
  }
  try {
    await SecureStore.deleteItemAsync(key);
  } catch (error) {
    throw new SecureStorageError("delete", key, error);
  }
}

/**
 * One-time migration from legacy AsyncStorage.
 * The legacy value is removed only after the SecureStore write is read back
 * successfully, so a failed migration cannot discard the only credential copy.
 */
export async function migrateFromAsyncStorage(keys: string[]): Promise<void> {
  if (USE_ASYNC_TEST_FALLBACK) return;

  for (const key of keys) {
    const legacy = await AsyncStorage.getItem(key);
    if (legacy == null) continue;

    try {
      const existing = await getSecureItem(key);
      if (existing == null) {
        await setSecureItem(key, legacy);
        const verified = await getSecureItem(key);
        if (verified !== legacy) {
          throw new Error("SecureStore verification did not match the migrated value");
        }
      }
      await AsyncStorage.removeItem(key);
    } catch (error) {
      throw new SecureStorageError("migrate", key, error);
    }
  }
}
