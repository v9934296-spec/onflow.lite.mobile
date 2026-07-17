import AsyncStorage from "@react-native-async-storage/async-storage";
import { LoadResult, LoggedClip, StorageResult } from "./types";
import { scopedKey } from "./storage/userScope";

const KEY = "onflow_lite_log_v1";

export async function loadLog(): Promise<LoadResult<LoggedClip[]>> {
  try {
    const raw = await AsyncStorage.getItem(scopedKey(KEY));
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

export async function saveLog(log: LoggedClip[]): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(scopedKey(KEY), JSON.stringify(log));
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Failed to save log" };
  }
}

export async function clearLog(): Promise<StorageResult> {
  try {
    await AsyncStorage.removeItem(scopedKey(KEY));
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Failed to clear log" };
  }
}

export async function deleteLogEntry(id: string): Promise<StorageResult> {
  const { data } = await loadLog();
  return saveLog(data.filter((entry) => entry.id !== id));
}
