import AsyncStorage from "@react-native-async-storage/async-storage";
import { LoadResult, LoggedClip, StorageResult } from "./types";

const KEY = "onflow_lite_log_v1";

export async function loadLog(): Promise<LoadResult<LoggedClip[]>> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return { data: raw ? (JSON.parse(raw) as LoggedClip[]) : [] };
  } catch (e) {
    return { data: [], loadError: e instanceof Error ? e.message : "Failed to load log" };
  }
}

export async function saveLog(log: LoggedClip[]): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(log));
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Failed to save log" };
  }
}

export async function clearLog(): Promise<StorageResult> {
  try {
    await AsyncStorage.removeItem(KEY);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Failed to clear log" };
  }
}

export async function deleteLogEntry(id: string): Promise<StorageResult> {
  const { data } = await loadLog();
  return saveLog(data.filter((e) => e.id !== id));
}
