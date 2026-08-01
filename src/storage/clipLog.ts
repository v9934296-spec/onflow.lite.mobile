import AsyncStorage from "@react-native-async-storage/async-storage";
import { LoadResult, LoggedClip, StorageResult } from "../types";
import { userScopedStorageKey } from "./userScopedStorage";

function keyFor(userId: string): string {
  return userScopedStorageKey(userId, "clipLog");
}

export async function loadLog(userId: string): Promise<LoadResult<LoggedClip[]>> {
  try {
    const raw = await AsyncStorage.getItem(keyFor(userId));
    if (!raw) return { data: [] };

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return { data: [], loadError: "Saved session log has an invalid format" };
    }

    return { data: parsed as LoggedClip[] };
  } catch (error) {
    return {
      data: [],
      loadError: error instanceof Error ? error.message : "Failed to load log",
    };
  }
}

export async function saveLog(userId: string, log: LoggedClip[]): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(keyFor(userId), JSON.stringify(log));
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Failed to save log" };
  }
}

export async function clearLog(userId: string): Promise<StorageResult> {
  try {
    await AsyncStorage.removeItem(keyFor(userId));
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Failed to clear log" };
  }
}
