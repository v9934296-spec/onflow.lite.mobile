export type EvidenceTag = "DETECTED" | "ESTIMATE" | "NO EVIDENCE";
export type EvidenceClass = EvidenceTag;
export type ManualOutcome = "landed" | "missed" | "unsure";

export interface Observation {
  text: string;
  tag: EvidenceTag;
}

export interface BreakdownItem {
  k: string;
  v: number;
}

export interface Receipt {
  id: string;
  label: string;
  source: "measured" | "detected" | "estimated" | "none";
  detail: string;
}

export interface Analysis {
  trickCalled: string;
  trickOnFilm: string | null;
  mismatch: boolean;
  abstained: boolean;
  rating: number | null;
  verdict: string;
  observations: Observation[];
  breakdown: BreakdownItem[] | null;
  workOn: string;
  styleNote: string | null;
  source: "sample" | "user";
  selfReportOnly?: boolean;
  engineVersion: string;
  evidenceClass: EvidenceClass;
  confidence: number; // 0–100
  receipts: Receipt[];
  abstainReason: string | null;
}

export interface SampleClip {
  id: string;
  label: string;
  canonical: string;
  spot: string;
  durationSec: number;
}

export interface ManualLog {
  manualOutcome: ManualOutcome;
  attempts: number;
  spot: string;
  notes: string;
}

export interface LoggedClip {
  id: string;
  loggedAt: string;
  analysis: Analysis;
  manualLog?: ManualLog;
  /** @deprecated use manualLog.manualOutcome */
  landed?: boolean | null;
}

export interface LandedAttempt {
  id: string;
  trick: string;
  manualOutcome: ManualOutcome;
  attempts: number;
  spot: string;
  notes: string;
  landed: boolean;
  loggedAt: string;
  source: "sample" | "user";
}

export type StorageResult = { ok: true } | { ok: false; error: string };

export interface LoadResult<T> {
  data: T;
  loadError?: string;
}
