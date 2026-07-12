import { useRouter, useSegments } from "expo-router";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ActivityIndicator, View } from "react-native";

import { setAuthExpiredCallback, setAuthTokenProvider } from "../api/auth";
import { isExpoApiUrlConfigured } from "../api/config";
import { C } from "../theme";
import { useAccount } from "./accountContext";
import { bootstrapDevSessionIfNeeded, isDevSkipSignInEnabled } from "./devSkipAuth";
import { clearOnflowSession, loadOnflowSession } from "./onflowSession";

export type AuthPhase = "loading" | "signed_out" | "signed_in";

type AuthContextValue = {
  phase: AuthPhase;
  authError: string | null;
  dismissAuthError: () => void;
  signOut: () => Promise<void>;
  /** Call after saving a new session token — validates /me and updates auth phase. */
  completeSignIn: () => Promise<boolean>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function authStorageMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : "Unknown secure storage error";
  return `Secure credential storage is unavailable. ${detail}`;
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const { phase } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (phase === "loading") return;
    const onSignIn = segments[0] === "sign-in";
    if (phase === "signed_out" && !onSignIn) {
      router.replace("/sign-in");
    } else if (phase === "signed_in" && onSignIn) {
      router.replace("/");
    }
  }, [phase, segments, router]);

  if (phase === "loading") {
    return (
      <View style={{ flex: 1, backgroundColor: C.charcoal, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={C.volt} />
      </View>
    );
  }

  return <>{children}</>;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { refreshUser, clearUser } = useAccount();
  const [phase, setPhase] = useState<AuthPhase>("loading");
  const [authError, setAuthError] = useState<string | null>(null);
  const handlingExpiry = useRef(false);

  const dismissAuthError = useCallback(() => setAuthError(null), []);

  const signOut = useCallback(async () => {
    setAuthError(null);
    try {
      await clearOnflowSession();
    } catch (error) {
      setAuthError(authStorageMessage(error));
      throw error;
    }
    clearUser();
    setPhase("signed_out");
  }, [clearUser]);

  const completeSignIn = useCallback(async (): Promise<boolean> => {
    setAuthError(null);
    const valid = await refreshUser();
    if (!valid) {
      clearUser();
      setPhase("signed_out");
      try {
        await clearOnflowSession();
      } catch (error) {
        setAuthError(authStorageMessage(error));
        throw error;
      }
      return false;
    }
    setPhase("signed_in");
    return true;
  }, [refreshUser, clearUser]);

  const handleSessionExpired = useCallback(async () => {
    if (handlingExpiry.current) return;
    handlingExpiry.current = true;
    try {
      try {
        await clearOnflowSession();
      } catch (error) {
        setAuthError(authStorageMessage(error));
      }
      clearUser();
      setPhase("signed_out");
      router.replace({ pathname: "/sign-in", params: { reason: "session_expired" } });
    } finally {
      handlingExpiry.current = false;
    }
  }, [clearUser, router]);

  useEffect(() => {
    setAuthTokenProvider(async () => {
      const session = await loadOnflowSession();
      return session?.token ?? null;
    });
    setAuthExpiredCallback(() => {
      void handleSessionExpired();
    });
    return () => {
      setAuthTokenProvider(null);
      setAuthExpiredCallback(null);
    };
  }, [handleSessionExpired]);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        if (!isExpoApiUrlConfigured()) {
          if (!cancelled) setPhase("signed_out");
          return;
        }

        if (isDevSkipSignInEnabled()) {
          const existing = await loadOnflowSession();
          if (!existing?.token) {
            const { ok } = await bootstrapDevSessionIfNeeded();
            if (!ok) {
              if (!cancelled) setPhase("signed_out");
              return;
            }
          }
          const valid = await refreshUser();
          if (!cancelled) {
            setPhase(valid ? "signed_in" : "signed_out");
            if (!valid) await clearOnflowSession();
          }
          return;
        }

        const session = await loadOnflowSession();
        if (!session?.token) {
          if (!cancelled) setPhase("signed_out");
          return;
        }

        const valid = await refreshUser();
        if (cancelled) return;
        if (valid) {
          setPhase("signed_in");
        } else {
          await clearOnflowSession();
          clearUser();
          setPhase("signed_out");
        }
      } catch (error) {
        if (cancelled) return;
        setAuthError(authStorageMessage(error));
        clearUser();
        setPhase("signed_out");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshUser, clearUser]);

  const value = useMemo(
    () => ({ phase, authError, dismissAuthError, signOut, completeSignIn }),
    [phase, authError, dismissAuthError, signOut, completeSignIn],
  );

  return (
    <AuthContext.Provider value={value}>
      <AuthGate>{children}</AuthGate>
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
