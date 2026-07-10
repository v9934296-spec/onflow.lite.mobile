import AsyncStorage from "@react-native-async-storage/async-storage";
import { LoggedClip } from "./types";

const KEY = "onflow_lite_log_v1";

export async function loadLog(): Promise<LoggedClip[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as LoggedClip[]) : [];
  } catch {
    return [];
  }
}

export async function saveLog(log: LoggedClip[]): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(log));
  } catch {
    // lite build: fail silently, log stays in memory for the session
  }
}

export async function clearLog(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {}
}
