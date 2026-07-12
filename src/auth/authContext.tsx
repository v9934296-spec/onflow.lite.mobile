import { useRouter, useSegments } from "expo-router";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ActivityIndicator, View } from "react-native";

import { setAuthExpiredCallback, setAuthTokenProvider } from "../api/auth";
import { isExpoApiUrlConfigured } from "../api/config";
import { useAccount } from "./accountContext";
import { bootstrapDevSessionIfNeeded, isDevSkipSignInEnabled } from "./devSkipAuth";
import { clearOnflowSession, loadOnflowSession } from "./onflowSession";
import { C } from "../theme";

export type AuthPhase = "loading" | "signed_out" | "signed_in";

type AuthContextValue = {
  phase: AuthPhase;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

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

  const signOut = useCallback(async () => {
    await clearOnflowSession();
    clearUser();
    setPhase("signed_out");
  }, [clearUser]);

  const handleSessionExpired = useCallback(async () => {
    await clearOnflowSession();
    clearUser();
    setPhase("signed_out");
    router.replace({ pathname: "/sign-in", params: { reason: "session_expired" } });
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
    })();

    return () => {
      cancelled = true;
    };
  }, [refreshUser, clearUser]);

  const value = useMemo(() => ({ phase, signOut }), [phase, signOut]);

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
