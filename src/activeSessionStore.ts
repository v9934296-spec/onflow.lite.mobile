import AsyncStorage from "@react-native-async-storage/async-storage";

const ACTIVE_SESSION_KEY = "onflow.activeSession.v2";

export async function saveActiveSessionId(sessionId: string): Promise<void> {
  const sid = sessionId.trim();
  if (!sid) return;
  await AsyncStorage.setItem(ACTIVE_SESSION_KEY, sid);
}

export async function loadActiveSessionId(): Promise<string | null> {
  const raw = await AsyncStorage.getItem(ACTIVE_SESSION_KEY);
  const sid = raw?.trim();
  return sid ? sid : null;
}

export async function clearActiveSessionId(): Promise<void> {
  await AsyncStorage.removeItem(ACTIVE_SESSION_KEY);
}
