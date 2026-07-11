import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { track } from "./analytics";
import { appendAttempt, loadAttempts } from "./progress";
import { Analysis, LandedAttempt, LoggedClip, ManualLog } from "./types";
import { clearLog as clearLogStorage, loadLog, saveLog } from "./storage";

interface SessionState {
  trick: string | null;
  setTrick: (t: string | null) => void;
  analysis: Analysis | null;
  setAnalysis: (a: Analysis | null) => void;
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

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [trick, setTrick] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [log, setLog] = useState<LoggedClip[]>([]);
  const [attempts, setAttempts] = useState<LandedAttempt[]>([]);
  const [storageWarning, setStorageWarning] = useState<string | null>(null);

  const warnStorage = useCallback((message: string) => {
    setStorageWarning(message);
    track("storage_error", { message });
  }, []);

  useEffect(() => {
    loadLog().then(({ data, loadError }) => {
      setLog(data);
      if (loadError) warnStorage(`Couldn't load session log — ${loadError}`);
    });
    loadAttempts().then(({ data, loadError }) => {
      setAttempts(data);
      if (loadError) warnStorage(`Couldn't load progress — ${loadError}`);
    });
  }, [warnStorage]);

  const reportManualLog = useCallback(
    async (manual: ManualLog) => {
      if (!analysis) return;

      const entry: LoggedClip = {
        id: `${Date.now()}`,
        loggedAt: new Date().toISOString(),
        analysis,
        manualLog: manual,
        landed: manual.manualOutcome === "landed",
      };

      const attempt: LandedAttempt = {
        id: entry.id,
        trick: analysis.trickCalled,
        manualOutcome: manual.manualOutcome,
        attempts: manual.attempts,
        spot: manual.spot,
        notes: manual.notes,
        landed: manual.manualOutcome === "landed",
        loggedAt: entry.loggedAt,
        source: analysis.source,
      };

      setLog((prev) => {
        const next = [...prev, entry];
        saveLog(next).then((result) => {
          if (!result.ok) warnStorage("Couldn't save — clip kept in memory this session");
        });
        return next;
      });

      setAttempts((prev) => {
        const next = [...prev, attempt];
        appendAttempt(attempt).then((result) => {
          if (!result.ok) warnStorage("Couldn't save progress — kept in memory this session");
        });
        return next;
      });

      track("land_reported", {
        trick: analysis.trickCalled,
        outcome: manual.manualOutcome,
        attempts: manual.attempts,
        source: analysis.source,
      });
    },
    [analysis, warnStorage],
  );

  const deleteClip = useCallback(
    async (id: string) => {
      setLog((prev) => {
        const next = prev.filter((e) => e.id !== id);
        saveLog(next).then((result) => {
          if (!result.ok) warnStorage("Couldn't delete clip from storage");
        });
        return next;
      });
      setAttempts((prev) => prev.filter((a) => a.id !== id));
    },
    [warnStorage],
  );

  const clearSessionLog = useCallback(async () => {
    const result = await clearLogStorage();
    if (!result.ok) {
      warnStorage("Couldn't clear log from storage");
      return;
    }
    setLog([]);
    track("log_cleared");
  }, [warnStorage]);

  const resetLoop = () => {
    setTrick(null);
    setAnalysis(null);
  };

  return (
    <Ctx.Provider
      value={{
        trick,
        setTrick,
        analysis,
        setAnalysis,
        log,
        attempts,
        storageWarning,
        dismissStorageWarning: () => setStorageWarning(null),
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
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
