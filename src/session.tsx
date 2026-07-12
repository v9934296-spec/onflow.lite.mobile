import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { track } from "./analytics";
import { loadAttempts, saveAttempts } from "./progress";
import { Analysis, LandedAttempt, LoggedClip, ManualLog, StorageResult } from "./types";
import type { SelectedTrick } from "./tricks/types";
import { clearLog as clearLogStorage, loadLog, saveLog } from "./storage";

interface SessionState {
  isHydrated: boolean;
  trick: string | null;
  selectedTrick: SelectedTrick | null;
  setTrick: (trick: string | null) => void;
  setSelectedTrick: (trick: SelectedTrick | null) => void;
  analysis: Analysis | null;
  setAnalysis: (analysis: Analysis | null) => void;
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
  const [isHydrated, setIsHydrated] = useState(false);
  const [trick, setTrickState] = useState<string | null>(null);
  const [selectedTrick, setSelectedTrickState] = useState<SelectedTrick | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
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

    const hydrate = async () => {
      try {
        const [logResult, attemptsResult] = await Promise.all([loadLog(), loadAttempts()]);
        if (cancelled) return;

        // Scripted sample clips are demonstrations, never part of the skater's
        // self-reported progress record. This also cleans legacy sample attempts.
        const userAttempts = attemptsResult.data.filter((attempt) => attempt.source === "user");

        logRef.current = logResult.data;
        attemptsRef.current = userAttempts;
        setLog(logResult.data);
        setAttempts(userAttempts);
        setIsHydrated(true);

        if (logResult.loadError) warnStorage(`Couldn't load session log — ${logResult.loadError}`);
        if (attemptsResult.loadError) warnStorage(`Couldn't load progress — ${attemptsResult.loadError}`);

        if (userAttempts.length !== attemptsResult.data.length) {
          const cleanupResult = await saveAttempts(userAttempts);
          if (!cleanupResult.ok && !cancelled) {
            warnStorage("Couldn't remove legacy sample data from saved progress");
          }
        }
      } catch (error) {
        if (cancelled) return;
        setIsHydrated(true);
        warnStorage(
          `Couldn't restore saved session — ${error instanceof Error ? error.message : "unknown error"}`,
        );
      }
    };

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [warnStorage]);

  const reportManualLog = useCallback(
    async (manual: ManualLog) => {
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
        saveLog(nextLog),
        analysis.source === "user"
          ? saveAttempts(nextAttempts)
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
    [analysis, warnStorage],
  );

  const deleteClip = useCallback(
    async (id: string) => {
      const nextLog = logRef.current.filter((entry) => entry.id !== id);
      const nextAttempts = attemptsRef.current.filter((attempt) => attempt.id !== id);

      logRef.current = nextLog;
      attemptsRef.current = nextAttempts;
      setLog(nextLog);
      setAttempts(nextAttempts);

      const [logResult, attemptsResult] = await Promise.all([
        saveLog(nextLog),
        saveAttempts(nextAttempts),
      ]);

      const failures = [
        storageFailure(logResult, "Couldn't delete the clip from the saved log"),
        storageFailure(attemptsResult, "Couldn't delete the clip from saved progress"),
      ].filter((message): message is string => Boolean(message));

      if (failures.length > 0) warnStorage(failures.join(" · "));
    },
    [warnStorage],
  );

  const clearSessionLog = useCallback(async () => {
    const result = await clearLogStorage();
    if (!result.ok) {
      warnStorage("Couldn't clear log from storage");
      return;
    }

    logRef.current = [];
    setLog([]);
    track("log_cleared");
  }, [warnStorage]);

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
