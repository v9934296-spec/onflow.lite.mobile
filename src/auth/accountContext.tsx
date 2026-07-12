import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { fetchAccountMe } from "../api/authApi";
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
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<boolean> => {
    setAccountLoading(true);
    try {
      const result = await fetchAccountMe();
      if (!result.ok) {
        setUser(null);
        return false;
      }
      setUser(result.data);
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
