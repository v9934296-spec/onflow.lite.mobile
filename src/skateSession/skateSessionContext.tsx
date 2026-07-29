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
  saveLastRecapSessionId,
} from "../activeSessionStore";
import { createSkateSession, fetchSkateSession, updateSkateSession } from "../api/sessionApi";
import { useAccount } from "../auth/accountContext";
import { useAuth } from "../auth/authContext";
import { buildSessionRecap } from "../sessionRecap/buildSessionRecap";
import { saveCompletedSessionRecap } from "../sessionRecap/completedSessionStore";
import { loadSessionAttempts } from "../sessionAttempts/sessionAttemptStore";
import type { SkateSession } from "../types/api/session";
import { isSkateSessionActive } from "../types/api/session";
import type { SessionRecap } from "../types/sessionRecap";
import {
  clearPendingSessionCompletion,
  loadPendingSessionCompletion,
  savePendingSessionCompletion,
  type PendingSessionCompletion,
} from "./sessionCompletionStore";

export type SkateSessionHydrateState = "idle" | "loading" | "ready" | "error";

export type EndSessionResult =
  | { ok: true; recap: SessionRecap }
  | { ok: false; error: string };

type SkateSessionContextValue = {
  activeSession: SkateSession | null;
  hasActiveSession: boolean;
  hydrateState: SkateSessionHydrateState;
  hydrateError: string | null;
  isCreating: boolean;
  createError: string | null;
  isEnding: boolean;
  endError: string | null;
  startSession: () => Promise<boolean>;
  continueSession: () => boolean;
  refreshActiveSession: () => Promise<void>;
  endSession: () => Promise<EndSessionResult>;
  dismissEndError: () => void;
};

const SkateSessionContext = createContext<SkateSessionContextValue | null>(null);

async function persistCompletedSession(
  userId: string,
  pending: PendingSessionCompletion,
): Promise<{ ok: true } | { ok: false; error: string }> {
  const saveResult = await saveCompletedSessionRecap(userId, pending.recap);
  if (!saveResult.ok) return saveResult;

  try {
    await saveLastRecapSessionId(userId, pending.sessionId);
    await clearActiveSessionId(userId);
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to finalize session storage",
    };
  }

  const clearJournal = await clearPendingSessionCompletion(userId);
  return clearJournal.ok ? { ok: true } : clearJournal;
}

async function recoverPendingCompletion(
  userId: string,
  pending: PendingSessionCompletion,
): Promise<{ ok: true } | { ok: false; error: string }> {
  const fetched = await fetchSkateSession(pending.sessionId);
  if (!fetched.ok) return { ok: false, error: fetched.error.message };

  if (fetched.data && isSkateSessionActive(fetched.data)) {
    const updated = await updateSkateSession(pending.sessionId, { ended_at: pending.endedAt });
    if (!updated.ok) return { ok: false, error: updated.error.message };
  }

  return persistCompletedSession(userId, pending);
}

export function SkateSessionProvider({ children }: { children: React.ReactNode }) {
  const { phase } = useAuth();
  const { user } = useAccount();
  const userId = user?.user_id ?? null;
  const [activeSession, setActiveSession] = useState<SkateSession | null>(null);
  const [hydrateState, setHydrateState] = useState<SkateSessionHydrateState>("idle");
  const [hydrateError, setHydrateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [isEnding, setIsEnding] = useState(false);
  const [endError, setEndError] = useState<string | null>(null);
  const creatingRef = useRef(false);
  const endingRef = useRef(false);

  const refreshActiveSession = useCallback(async () => {
    if (!userId || phase !== "signed_in") {
      setActiveSession(null);
      setHydrateState("idle");
      return;
    }

    setHydrateState("loading");
    setHydrateError(null);

    const pendingResult = await loadPendingSessionCompletion(userId);
    if (pendingResult.loadError) {
      setHydrateState("error");
      setHydrateError(pendingResult.loadError);
      return;
    }
    if (pendingResult.data) {
      const recovered = await recoverPendingCompletion(userId, pendingResult.data);
      if (!recovered.ok) {
        setHydrateState("error");
        setHydrateError(recovered.error);
        return;
      }
    }

    const storedId = await loadActiveSessionId(userId);
    if (!storedId) {
      setActiveSession(null);
      setHydrateState("ready");
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
      await clearActiveSessionId(userId);
      setActiveSession(null);
      setHydrateState("ready");
      return;
    }

    setActiveSession(result.data);
    setHydrateState("ready");
  }, [phase, userId]);

  useEffect(() => {
    if (phase !== "signed_in" || !userId) {
      setActiveSession(null);
      setHydrateState("idle");
      setHydrateError(null);
      setCreateError(null);
      setEndError(null);
      return;
    }

    let cancelled = false;
    setHydrateState("loading");
    setHydrateError(null);

    void (async () => {
      const pendingResult = await loadPendingSessionCompletion(userId);
      if (cancelled) return;
      if (pendingResult.loadError) {
        setHydrateState("error");
        setHydrateError(pendingResult.loadError);
        return;
      }
      if (pendingResult.data) {
        const recovered = await recoverPendingCompletion(userId, pendingResult.data);
        if (cancelled) return;
        if (!recovered.ok) {
          setHydrateState("error");
          setHydrateError(recovered.error);
          return;
        }
      }

      const storedId = await loadActiveSessionId(userId);
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
        await clearActiveSessionId(userId);
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
  }, [phase, userId]);

  const startSession = useCallback(async (): Promise<boolean> => {
    if (!userId || creatingRef.current || isCreating) return false;
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
      await saveActiveSessionId(userId, result.data.id);
      setActiveSession(result.data);
      setHydrateState("ready");
      setHydrateError(null);
      return true;
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Could not save the active session");
      return false;
    } finally {
      creatingRef.current = false;
      setIsCreating(false);
    }
  }, [activeSession, isCreating, userId]);

  const endSession = useCallback(async (): Promise<EndSessionResult> => {
    if (!userId || !activeSession || endingRef.current || isEnding) {
      return { ok: false, error: "No active session to end." };
    }

    const sessionId = activeSession.id;
    const endedAt = new Date().toISOString();

    endingRef.current = true;
    setIsEnding(true);
    setEndError(null);

    try {
      const attemptsResult = await loadSessionAttempts(userId, sessionId);
      if (attemptsResult.loadError) {
        setEndError(attemptsResult.loadError);
        return { ok: false, error: attemptsResult.loadError };
      }

      const recap = buildSessionRecap(activeSession, attemptsResult.data, endedAt);
      const pending: PendingSessionCompletion = { sessionId, endedAt, recap };
      const journalResult = await savePendingSessionCompletion(userId, pending);
      if (!journalResult.ok) {
        setEndError(journalResult.error);
        return { ok: false, error: journalResult.error };
      }

      const updateResult = await updateSkateSession(sessionId, { ended_at: endedAt });
      if (!updateResult.ok) {
        const fetched = await fetchSkateSession(sessionId);
        const alreadyEnded = fetched.ok && fetched.data && !isSkateSessionActive(fetched.data);
        if (!alreadyEnded) {
          const message = updateResult.error.message;
          setEndError(message);
          return { ok: false, error: message };
        }
      }

      const persisted = await persistCompletedSession(userId, pending);
      if (!persisted.ok) {
        setEndError(persisted.error);
        return { ok: false, error: persisted.error };
      }

      setActiveSession(null);
      setHydrateState("ready");
      return { ok: true, recap };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not finish the session";
      setEndError(message);
      return { ok: false, error: message };
    } finally {
      endingRef.current = false;
      setIsEnding(false);
    }
  }, [activeSession, isEnding, userId]);

  const dismissEndError = useCallback(() => setEndError(null), []);

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
      isEnding,
      endError,
      startSession,
      continueSession,
      refreshActiveSession,
      endSession,
      dismissEndError,
    }),
    [
      activeSession,
      hasActiveSession,
      hydrateState,
      hydrateError,
      isCreating,
      createError,
      isEnding,
      endError,
      startSession,
      continueSession,
      refreshActiveSession,
      endSession,
      dismissEndError,
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
