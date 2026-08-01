import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import { track } from "./analytics";
import { loadPendingAnalysisJob } from "./analysis/pendingAnalysisStore";
import { useAccount } from "./auth/accountContext";
import { loadAttempts, saveAttempts } from "./progress";
import { clearLog as clearLogStorage, loadLog, saveLog } from "./storage/clipLog";
import type { SelectedTrick } from "./tricks/types";
import type { Analysis, LandedAttempt, LoggedClip, ManualLog, StorageResult } from "./types";

interface SessionState {
  isHydrated: boolean;
  trick: string | null;
  selectedTrick: SelectedTrick | null;
  setTrick: (trick: string | null) => void;
  setSelectedTrick: (trick: SelectedTrick | null) => void;
  analysis: Analysis | null;
  setAnalysis: (analysis: Analysis | null) => void;
  pendingClipJobId: string | null;
  setPendingClipJobId: (jobId: string | null) => void;
  log: LoggedClip[];
  attempts: LandedAttempt[];
  storageWarning: string | null;
  dismissStorageWarning: () => void;
  reportManualLog: (manual: ManualLog) => Promise<void>;
  deleteClip: (id: string) => Promise<void>;
  clearSessionLog: () => Promise<void>;
  resetLoop: () => void;
}

const Ctx = createContext<SessionState | null>(null);

function newEntryId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function storageFailure(result: StorageResult, fallback: string): string | null {
  return result.ok ? null : result.error || fallback;
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAccount();
  const userId = user?.user_id ?? null;
  const [isHydrated, setIsHydrated] = useState(false);
  const [trick, setTrickState] = useState<string | null>(null);
  const [selectedTrick, setSelectedTrickState] = useState<SelectedTrick | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [pendingClipJobId, setPendingClipJobId] = useState<string | null>(null);
  const [log, setLog] = useState<LoggedClip[]>([]);
  const [attempts, setAttempts] = useState<LandedAttempt[]>([]);
  const [storageWarning, setStorageWarning] = useState<string | null>(null);
  const logRef = useRef<LoggedClip[]>([]);
  const attemptsRef = useRef<LandedAttempt[]>([]);

  const warnStorage = useCallback((message: string) => {
    setStorageWarning(message);
    track("storage_error", { message });
  }, []);

  const dismissStorageWarning = useCallback(() => setStorageWarning(null), []);

  useEffect(() => {
    let cancelled = false;

    setIsHydrated(false);
    setStorageWarning(null);
    setTrickState(null);
    setSelectedTrickState(null);
    setAnalysis(null);
    setPendingClipJobId(null);
    logRef.current = [];
    attemptsRef.current = [];
    setLog([]);
    setAttempts([]);

    if (!userId) {
      setIsHydrated(true);
      return () => {
        cancelled = true;
      };
    }

    const hydrate = async () => {
      try {
        const [logResult, attemptsResult, pendingResult] = await Promise.all([
          loadLog(userId),
          loadAttempts(userId),
          loadPendingAnalysisJob(userId),
        ]);
        if (cancelled) return;

        const userAttempts = attemptsResult.data.filter((attempt) => attempt.source === "user");
        logRef.current = logResult.data;
        attemptsRef.current = userAttempts;
        setLog(logResult.data);
        setAttempts(userAttempts);

        if (pendingResult.data) {
          setPendingClipJobId(pendingResult.data.jobId);
          setTrickState(pendingResult.data.trickName);
          setSelectedTrickState(pendingResult.data.selectedTrick);
        }

        if (logResult.loadError) warnStorage(`Couldn't load session log — ${logResult.loadError}`);
        if (attemptsResult.loadError) warnStorage(`Couldn't load progress — ${attemptsResult.loadError}`);
        if (pendingResult.loadError) warnStorage(`Couldn't restore analysis — ${pendingResult.loadError}`);

        if (userAttempts.length !== attemptsResult.data.length) {
          const cleanupResult = await saveAttempts(userId, userAttempts);
          if (!cleanupResult.ok && !cancelled) {
            warnStorage("Couldn't remove legacy sample data from saved progress");
          }
        }
      } catch (error) {
        if (cancelled) return;
        warnStorage(
          `Couldn't restore saved session — ${error instanceof Error ? error.message : "unknown error"}`,
        );
      } finally {
        if (!cancelled) setIsHydrated(true);
      }
    };

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [userId, warnStorage]);

  const reportManualLog = useCallback(
    async (manual: ManualLog) => {
      if (!userId) throw new Error("Sign in before saving an attempt.");
      if (!analysis) throw new Error("No active analysis is available to log.");

      const entry: LoggedClip = {
        id: newEntryId(),
        loggedAt: new Date().toISOString(),
        analysis,
        manualLog: manual,
        landed: manual.manualOutcome === "landed",
      };

      const nextLog = [...logRef.current, entry];
      logRef.current = nextLog;
      setLog(nextLog);

      let nextAttempts = attemptsRef.current;
      if (analysis.source === "user") {
        const attempt: LandedAttempt = {
          id: entry.id,
          trick: analysis.trickCalled,
          manualOutcome: manual.manualOutcome,
          attempts: manual.attempts,
          spot: manual.spot,
          notes: manual.notes,
          landed: manual.manualOutcome === "landed",
          loggedAt: entry.loggedAt,
          source: "user",
        };
        nextAttempts = [...attemptsRef.current, attempt];
        attemptsRef.current = nextAttempts;
        setAttempts(nextAttempts);
      }

      const [logResult, attemptsResult] = await Promise.all([
        saveLog(userId, nextLog),
        analysis.source === "user"
          ? saveAttempts(userId, nextAttempts)
          : Promise.resolve<StorageResult>({ ok: true }),
      ]);

      const failures = [
        storageFailure(logResult, "Couldn't save the session log"),
        storageFailure(attemptsResult, "Couldn't save progress"),
      ].filter((message): message is string => Boolean(message));

      if (failures.length > 0) {
        warnStorage(`${failures.join(" · ")} — data is kept in memory for this session`);
      }

      track("land_reported", {
        trick: analysis.trickCalled,
        outcome: manual.manualOutcome,
        attempts: manual.attempts,
        source: analysis.source,
        countedTowardProgress: analysis.source === "user",
      });
    },
    [analysis, userId, warnStorage],
  );

  const deleteClip = useCallback(
    async (id: string) => {
      if (!userId) throw new Error("Sign in before changing the session log.");
      const nextLog = logRef.current.filter((entry) => entry.id !== id);
      const nextAttempts = attemptsRef.current.filter((attempt) => attempt.id !== id);

      logRef.current = nextLog;
      attemptsRef.current = nextAttempts;
      setLog(nextLog);
      setAttempts(nextAttempts);

      const [logResult, attemptsResult] = await Promise.all([
        saveLog(userId, nextLog),
        saveAttempts(userId, nextAttempts),
      ]);

      const failures = [
        storageFailure(logResult, "Couldn't delete the clip from the saved log"),
        storageFailure(attemptsResult, "Couldn't delete the clip from saved progress"),
      ].filter((message): message is string => Boolean(message));

      if (failures.length > 0) warnStorage(failures.join(" · "));
    },
    [userId, warnStorage],
  );

  const clearSessionLog = useCallback(async () => {
    if (!userId) throw new Error("Sign in before clearing the session log.");
    const result = await clearLogStorage(userId);
    if (!result.ok) {
      warnStorage("Couldn't clear log from storage");
      return;
    }

    logRef.current = [];
    setLog([]);
    track("log_cleared");
  }, [userId, warnStorage]);

  const setTrick = useCallback((value: string | null) => {
    setTrickState(value);
  }, []);

  const setSelectedTrick = useCallback((value: SelectedTrick | null) => {
    setSelectedTrickState(value);
    setTrickState(value?.canonicalName ?? null);
  }, []);

  const resetLoop = useCallback(() => {
    setTrickState(null);
    setSelectedTrickState(null);
    setAnalysis(null);
  }, []);

  return (
    <Ctx.Provider
      value={{
        isHydrated,
        trick,
        selectedTrick,
        setTrick,
        setSelectedTrick,
        analysis,
        setAnalysis,
        pendingClipJobId,
        setPendingClipJobId,
        log,
        attempts,
        storageWarning,
        dismissStorageWarning,
        reportManualLog,
        deleteClip,
        clearSessionLog,
        resetLoop,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useSession(): SessionState {
  const context = useContext(Ctx);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
