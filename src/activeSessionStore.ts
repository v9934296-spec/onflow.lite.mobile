import AsyncStorage from "@react-native-async-storage/async-storage";
import { scopedKey } from "./storage/userScope";

const ACTIVE_SESSION_KEY = "onflow.activeSession.v2";
const LAST_RECAP_KEY = "onflow.lastRecapSession.v2";

export async function saveActiveSessionId(sessionId: string): Promise<void> {
  const sid = sessionId.trim();
  if (!sid) return;
  await AsyncStorage.setItem(scopedKey(ACTIVE_SESSION_KEY), sid);
}

export async function loadActiveSessionId(): Promise<string | null> {
  const raw = await AsyncStorage.getItem(scopedKey(ACTIVE_SESSION_KEY));
  const sid = raw?.trim();
  return sid ? sid : null;
}

export async function clearActiveSessionId(): Promise<void> {
  await AsyncStorage.removeItem(scopedKey(ACTIVE_SESSION_KEY));
}

export async function saveLastRecapSessionId(sessionId: string): Promise<void> {
  const sid = sessionId.trim();
  if (!sid) return;
  await AsyncStorage.setItem(scopedKey(LAST_RECAP_KEY), sid);
}

export async function loadLastRecapSessionId(): Promise<string | null> {
  const raw = await AsyncStorage.getItem(scopedKey(LAST_RECAP_KEY));
  const sid = raw?.trim();
  return sid ? sid : null;
}
