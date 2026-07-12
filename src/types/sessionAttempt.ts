export type SessionAttemptOutcome = "landed" | "missed";

export interface SessionAttempt {
  id: string;
  sessionId: string;
  trickId: string;
  canonicalName: string;
  outcome: SessionAttemptOutcome;
  loggedAt: string;
}

export interface CreateSessionAttemptInput {
  sessionId: string;
  trickId: string;
  canonicalName: string;
  outcome: SessionAttemptOutcome;
}

export function buildSessionAttempt(input: CreateSessionAttemptInput): SessionAttempt {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    sessionId: input.sessionId,
    trickId: input.trickId,
    canonicalName: input.canonicalName,
    outcome: input.outcome,
    loggedAt: new Date().toISOString(),
  };
}

export interface SessionAttemptCounts {
  total: number;
  landed: number;
  missed: number;
}

export function summarizeSessionAttempts(attempts: SessionAttempt[]): SessionAttemptCounts {
  let landed = 0;
  let missed = 0;
  for (const attempt of attempts) {
    if (attempt.outcome === "landed") landed += 1;
    else missed += 1;
  }
  return { total: attempts.length, landed, missed };
}
