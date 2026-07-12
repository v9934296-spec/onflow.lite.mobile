import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  clearActiveSessionId,
  loadActiveSessionId,
  saveActiveSessionId,
} from "../activeSessionStore";
import { createSkateSession, fetchSkateSession } from "../api/sessionApi";
import { useAuth } from "../auth/authContext";
import type { SkateSession } from "../types/api/session";
import { isSkateSessionActive } from "../types/api/session";

export type SkateSessionHydrateState = "idle" | "loading" | "ready" | "error";

type SkateSessionContextValue = {
  activeSession: SkateSession | null;
  hasActiveSession: boolean;
  hydrateState: SkateSessionHydrateState;
  hydrateError: string | null;
  isCreating: boolean;
  createError: string | null;
  startSession: () => Promise<boolean>;
  continueSession: () => boolean;
  refreshActiveSession: () => Promise<void>;
};

const SkateSessionContext = createContext<SkateSessionContextValue | null>(null);

export function SkateSessionProvider({ children }: { children: React.ReactNode }) {
  const { phase } = useAuth();
  const [activeSession, setActiveSession] = useState<SkateSession | null>(null);
  const [hydrateState, setHydrateState] = useState<SkateSessionHydrateState>("idle");
  const [hydrateError, setHydrateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const creatingRef = useRef(false);

  const refreshActiveSession = useCallback(async () => {
    const storedId = await loadActiveSessionId();
    if (!storedId) {
      setActiveSession(null);
      setHydrateState("ready");
      setHydrateError(null);
      return;
    }

    const result = await fetchSkateSession(storedId);
    if (!result.ok) {
      setActiveSession(null);
      setHydrateState("error");
      setHydrateError(result.error.message);
      return;
    }

    if (!result.data || !isSkateSessionActive(result.data)) {
      await clearActiveSessionId();
      setActiveSession(null);
      setHydrateState("ready");
      setHydrateError(null);
      return;
    }

    setActiveSession(result.data);
    setHydrateState("ready");
    setHydrateError(null);
  }, []);

  useEffect(() => {
    if (phase !== "signed_in") {
      setActiveSession(null);
      setHydrateState("idle");
      setHydrateError(null);
      setCreateError(null);
      return;
    }

    let cancelled = false;
    setHydrateState("loading");
    setHydrateError(null);
    void (async () => {
      const storedId = await loadActiveSessionId();
      if (cancelled) return;
      if (!storedId) {
        setActiveSession(null);
        setHydrateState("ready");
        return;
      }

      const result = await fetchSkateSession(storedId);
      if (cancelled) return;
      if (!result.ok) {
        setActiveSession(null);
        setHydrateState("error");
        setHydrateError(result.error.message);
        return;
      }

      if (!result.data || !isSkateSessionActive(result.data)) {
        await clearActiveSessionId();
        setActiveSession(null);
        setHydrateState("ready");
        return;
      }

      setActiveSession(result.data);
      setHydrateState("ready");
    })();

    return () => {
      cancelled = true;
    };
  }, [phase]);

  const startSession = useCallback(async (): Promise<boolean> => {
    if (creatingRef.current || isCreating) return false;
    if (isSkateSessionActive(activeSession)) return true;

    creatingRef.current = true;
    setIsCreating(true);
    setCreateError(null);
    try {
      const result = await createSkateSession();
      if (!result.ok) {
        setCreateError(result.error.message);
        return false;
      }
      await saveActiveSessionId(result.data.id);
      setActiveSession(result.data);
      setHydrateState("ready");
      return true;
    } finally {
      creatingRef.current = false;
      setIsCreating(false);
    }
  }, [activeSession, isCreating]);

  const continueSession = useCallback((): boolean => {
    return isSkateSessionActive(activeSession);
  }, [activeSession]);

  const hasActiveSession = isSkateSessionActive(activeSession);

  const value = useMemo(
    () => ({
      activeSession,
      hasActiveSession,
      hydrateState,
      hydrateError,
      isCreating,
      createError,
      startSession,
      continueSession,
      refreshActiveSession,
    }),
    [
      activeSession,
      hasActiveSession,
      hydrateState,
      hydrateError,
      isCreating,
      createError,
      startSession,
      continueSession,
      refreshActiveSession,
    ],
  );

  return <SkateSessionContext.Provider value={value}>{children}</SkateSessionContext.Provider>;
}

export function useSkateSession(): SkateSessionContextValue {
  const ctx = useContext(SkateSessionContext);
  if (!ctx) {
    throw new Error("useSkateSession must be used within SkateSessionProvider");
  }
  return ctx;
}
