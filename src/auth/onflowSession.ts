import {
  getSecureItem,
  migrateFromAsyncStorage,
  removeSecureItem,
  setSecureItem,
} from "./secureStorage";

const TOKEN_KEY = "onflow_session_token";
const USER_ID_KEY = "onflow_session_user_id";
const EMAIL_KEY = "onflow_session_email";
const LEGACY_KEYS = [TOKEN_KEY, USER_ID_KEY, EMAIL_KEY];

let migrated = false;

async function ensureMigrated(): Promise<void> {
  if (migrated) return;
  await migrateFromAsyncStorage(LEGACY_KEYS);
  migrated = true;
}

export type OnflowStoredSession = {
  token: string;
  userId: string;
  email: string;
};

export async function saveOnflowSession(session: OnflowStoredSession): Promise<void> {
  await ensureMigrated();
  await Promise.all([
    setSecureItem(TOKEN_KEY, session.token),
    setSecureItem(USER_ID_KEY, session.userId),
    setSecureItem(EMAIL_KEY, session.email),
  ]);
}

export async function loadOnflowSession(): Promise<OnflowStoredSession | null> {
  await ensureMigrated();
  const [token, userId, email] = await Promise.all([
    getSecureItem(TOKEN_KEY),
    getSecureItem(USER_ID_KEY),
    getSecureItem(EMAIL_KEY),
  ]);
  if (!token?.trim() || !userId?.trim()) return null;
  return { token: token.trim(), userId: userId.trim(), email: (email ?? "").trim() };
}

export async function clearOnflowSession(): Promise<void> {
  await ensureMigrated();
  await Promise.all([
    removeSecureItem(TOKEN_KEY),
    removeSecureItem(USER_ID_KEY),
    removeSecureItem(EMAIL_KEY),
  ]);
}

/** Reset migration flag — for tests only. */
export function resetSessionMigration(): void {
  migrated = false;
}
