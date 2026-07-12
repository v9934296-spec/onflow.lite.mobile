import { useCallback, useEffect, useState } from "react";
import { listCompletedSessionRecaps } from "../sessionRecap/completedSessionStore";
import { excludeActiveSessionFromHistory } from "./sessionHistoryFormat";
import type { SessionRecap } from "../types/sessionRecap";

interface UseSessionHistoryResult {
  sessions: SessionRecap[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useSessionHistory(activeSessionId: string | null): UseSessionHistoryResult {
  const [sessions, setSessions] = useState<SessionRecap[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await listCompletedSessionRecaps();
      const filtered = excludeActiveSessionFromHistory(result.data, activeSessionId);
      setSessions(filtered);
      if (result.loadError) setError(result.loadError);
    } catch (err) {
      setSessions([]);
      setError(err instanceof Error ? err.message : "Could not load session history");
    } finally {
      setIsLoading(false);
    }
  }, [activeSessionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { sessions, isLoading, error, refresh };
}
