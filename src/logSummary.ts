import { EvidenceClass, LoggedClip } from "./types";

export interface LogSummary {
  sessionClips: number;
  totalAttempts: number;
  landedCount: number;
  missedCount: number;
  unsureCount: number;
  landedPct: number;
  practicedTricks: string[];
  evidenceTally: Record<EvidenceClass, number>;
}

export function summarizeLog(log: LoggedClip[]): LogSummary {
  const withManual = log.filter((e) => e.manualLog);
  const totalAttempts = withManual.reduce((sum, e) => sum + (e.manualLog?.attempts ?? 1), 0);
  const landedCount = withManual.filter((e) => e.manualLog?.manualOutcome === "landed").length;
  const missedCount = withManual.filter((e) => e.manualLog?.manualOutcome === "missed").length;
  const unsureCount = withManual.filter((e) => e.manualLog?.manualOutcome === "unsure").length;
  const decided = landedCount + missedCount;
  const landedPct = decided > 0 ? Math.round((landedCount / decided) * 100) : 0;
  const practicedTricks = [...new Set(log.map((e) => e.analysis.trickCalled))];

  const evidenceTally: Record<EvidenceClass, number> = {
    DETECTED: 0,
    ESTIMATE: 0,
    "NO EVIDENCE": 0,
  };
  for (const entry of log) {
    evidenceTally[entry.analysis.evidenceClass]++;
  }

  return {
    sessionClips: log.length,
    totalAttempts,
    landedCount,
    missedCount,
    unsureCount,
    landedPct,
    practicedTricks,
    evidenceTally,
  };
}
