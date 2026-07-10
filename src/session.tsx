import React, { createContext, useContext, useEffect, useState } from "react";
import { Analysis, LoggedClip } from "./types";
import { loadLog, saveLog } from "./storage";

interface SessionState {
  trick: string | null;
  setTrick: (t: string | null) => void;
  analysis: Analysis | null;
  setAnalysis: (a: Analysis | null) => void;
  log: LoggedClip[];
  logClip: (a: Analysis) => void;
  resetLoop: () => void;
}

const Ctx = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [trick, setTrick] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [log, setLog] = useState<LoggedClip[]>([]);

  useEffect(() => {
    loadLog().then(setLog);
  }, []);

  const logClip = (a: Analysis) => {
    const entry: LoggedClip = {
      id: `${Date.now()}`,
      loggedAt: new Date().toISOString(),
      analysis: a,
    };
    setLog((prev) => {
      const next = [...prev, entry];
      saveLog(next);
      return next;
    });
  };

  const resetLoop = () => {
    setTrick(null);
    setAnalysis(null);
  };

  return (
    <Ctx.Provider value={{ trick, setTrick, analysis, setAnalysis, log, logClip, resetLoop }}>
      {children}
    </Ctx.Provider>
  );
}

export function useSession(): SessionState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
