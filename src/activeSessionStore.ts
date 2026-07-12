import AsyncStorage from "@react-native-async-storage/async-storage";

import { userScopedStorageKey } from "./storage/userScopedStorage";

function activeSessionKey(userId: string): string {
  return userScopedStorageKey(userId, "activeSession", 2);
}

function lastRecapKey(userId: string): string {
  return userScopedStorageKey(userId, "lastRecapSession", 2);
}

export async function saveActiveSessionId(userId: string, sessionId: string): Promise<void> {
  const sid = sessionId.trim();
  if (!sid) return;
  await AsyncStorage.setItem(activeSessionKey(userId), sid);
}

export async function loadActiveSessionId(userId: string): Promise<string | null> {
  const raw = await AsyncStorage.getItem(activeSessionKey(userId));
  const sid = raw?.trim();
  return sid ? sid : null;
}

export async function clearActiveSessionId(userId: string): Promise<void> {
  await AsyncStorage.removeItem(activeSessionKey(userId));
}

export async function saveLastRecapSessionId(userId: string, sessionId: string): Promise<void> {
  const sid = sessionId.trim();
  if (!sid) return;
  await AsyncStorage.setItem(lastRecapKey(userId), sid);
}

export async function loadLastRecapSessionId(userId: string): Promise<string | null> {
  const raw = await AsyncStorage.getItem(lastRecapKey(userId));
  const sid = raw?.trim();
  return sid ? sid : null;
}
