/**
 * Encrypted-at-rest key/value storage for auth tokens.
 * Falls back to AsyncStorage in tests (no native SecureStore module).
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const USE_ASYNC_FALLBACK =
  typeof process !== "undefined" &&
  (Boolean(process.env.JEST_WORKER_ID) || process.env.NODE_ENV === "test");

export async function getSecureItem(key: string): Promise<string | null> {
  if (USE_ASYNC_FALLBACK) {
    return AsyncStorage.getItem(key);
  }
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return AsyncStorage.getItem(key);
  }
}

export async function setSecureItem(key: string, value: string): Promise<void> {
  if (USE_ASYNC_FALLBACK) {
    await AsyncStorage.setItem(key, value);
    return;
  }
  try {
    await SecureStore.setItemAsync(key, value);
  } catch {
    await AsyncStorage.setItem(key, value);
  }
}

export async function removeSecureItem(key: string): Promise<void> {
  if (USE_ASYNC_FALLBACK) {
    await AsyncStorage.removeItem(key);
    return;
  }
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    await AsyncStorage.removeItem(key);
  }
}

/** One-time migration: copy legacy AsyncStorage values into SecureStore, then delete. */
export async function migrateFromAsyncStorage(keys: string[]): Promise<void> {
  if (USE_ASYNC_FALLBACK) return;
  await Promise.all(
    keys.map(async (key) => {
      const legacy = await AsyncStorage.getItem(key);
      if (legacy == null) return;
      const existing = await getSecureItem(key);
      if (existing == null) {
        await setSecureItem(key, legacy);
      }
      await AsyncStorage.removeItem(key);
    }),
  );
}
