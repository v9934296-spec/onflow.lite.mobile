import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

import { fetchAccountMe } from "../api/authApi";
import { flushAttemptOutbox } from "../sessionAttempts/attemptOutbox";
import { activateStorageForUser, setStorageUserId } from "../storage/userScope";
import type { AccountMe } from "../types/api/account";

type AccountContextValue = {
  user: AccountMe | null;
  accountLoading: boolean;
  refreshUser: () => Promise<boolean>;
  clearUser: () => void;
};

const AccountContext = createContext<AccountContextValue | null>(null);

export function AccountProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AccountMe | null>(null);
  const [accountLoading, setAccountLoading] = useState(false);

  const clearUser = useCallback(() => {
    setStorageUserId(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<boolean> => {
    setAccountLoading(true);
    try {
      const result = await fetchAccountMe();
      if (!result.ok) {
        setStorageUserId(null);
        setUser(null);
        return false;
      }
      await activateStorageForUser(result.data.user_id);
      setUser(result.data);
      // Drain offline attempt outbox after identity is known.
      void flushAttemptOutbox();
      return true;
    } finally {
      setAccountLoading(false);
    }
  }, []);

  const value = useMemo(
    () => ({ user, accountLoading, refreshUser, clearUser }),
    [user, accountLoading, refreshUser, clearUser],
  );

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export function useAccount(): AccountContextValue {
  const ctx = useContext(AccountContext);
  if (!ctx) {
    throw new Error("useAccount must be used within AccountProvider");
  }
  return ctx;
}
