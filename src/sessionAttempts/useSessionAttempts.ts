import { useCallback, useEffect, useRef, useState } from "react";
import { track } from "../analytics";
import { hapticLand, hapticMiss } from "../haptics";
import { appendSessionAttempt, loadSessionAttempts } from "./sessionAttemptStore";
import {
  buildSessionAttempt,
  summarizeSessionAttempts,
  type SessionAttempt,
  type SessionAttemptCounts,
  type SessionAttemptOutcome,
} from "../types/sessionAttempt";
import type { SelectedTrick } from "../tricks/types";

interface UseSessionAttemptsResult {
  attempts: SessionAttempt[];
  counts: SessionAttemptCounts;
  isHydrated: boolean;
  isSubmitting: boolean;
  submitError: string | null;
  logAttempt: (trick: SelectedTrick, outcome: SessionAttemptOutcome) => Promise<boolean>;
  dismissSubmitError: () => void;
}

export function useSessionAttempts(sessionId: string | null): UseSessionAttemptsResult {
  const [attempts, setAttempts] = useState<SessionAttempt[]>([]);
  const [isHydrated, setIsHydrated] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const submitLock = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setIsHydrated(false);
    setSubmitError(null);

    if (!sessionId) {
      setAttempts([]);
      setIsHydrated(true);
      return;
    }

    void (async () => {
      const result = await loadSessionAttempts(sessionId);
      if (cancelled) return;
      setAttempts(result.data);
      setIsHydrated(true);
      if (result.loadError) setSubmitError(result.loadError);
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const dismissSubmitError = useCallback(() => setSubmitError(null), []);

  const logAttempt = useCallback(
    async (trick: SelectedTrick, outcome: SessionAttemptOutcome): Promise<boolean> => {
      if (!sessionId || submitLock.current || isSubmitting) return false;

      submitLock.current = true;
      setIsSubmitting(true);
      setSubmitError(null);

      const attempt = buildSessionAttempt({
        sessionId,
        trickId: trick.trickId,
        canonicalName: trick.canonicalName,
        outcome,
      });

      const previous = attempts;
      const optimistic = [...previous, attempt];
      setAttempts(optimistic);

      try {
        const result = await appendSessionAttempt(attempt);
        if (!result.ok) {
          setAttempts(previous);
          setSubmitError(result.error);
          return false;
        }

        track("session_attempt_logged", {
          session_id: sessionId,
          trick_id: trick.trickId,
          outcome,
        });
        if (outcome === "landed") void hapticLand();
        else void hapticMiss();
        return true;
      } catch (error) {
        setAttempts(previous);
        setSubmitError(error instanceof Error ? error.message : "Could not save attempt");
        return false;
      } finally {
        submitLock.current = false;
        setIsSubmitting(false);
      }
    },
    [attempts, isSubmitting, sessionId],
  );

  return {
    attempts,
    counts: summarizeSessionAttempts(attempts),
    isHydrated,
    isSubmitting,
    submitError,
    logAttempt,
    dismissSubmitError,
  };
}
