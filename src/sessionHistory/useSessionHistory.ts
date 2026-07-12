import { useCallback, useEffect, useState } from "react";

import { useAccount } from "../auth/accountContext";
import { listCompletedSessionRecaps } from "../sessionRecap/completedSessionStore";
import type { SessionRecap } from "../types/sessionRecap";
import { excludeActiveSessionFromHistory } from "./sessionHistoryFormat";

interface UseSessionHistoryResult {
  sessions: SessionRecap[];
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useSessionHistory(activeSessionId: string | null): UseSessionHistoryResult {
  const { user } = useAccount();
  const userId = user?.user_id ?? null;
  const [sessions, setSessions] = useState<SessionRecap[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    if (!userId) {
      setSessions([]);
      setIsLoading(false);
      return;
    }

    try {
      const result = await listCompletedSessionRecaps(userId);
      const filtered = excludeActiveSessionFromHistory(result.data, activeSessionId);
      setSessions(filtered);
      if (result.loadError) setError(result.loadError);
    } catch (err) {
      setSessions([]);
      setError(err instanceof Error ? err.message : "Could not load session history");
    } finally {
      setIsLoading(false);
    }
  }, [activeSessionId, userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { sessions, isLoading, error, refresh };
}
