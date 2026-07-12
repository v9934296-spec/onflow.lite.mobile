export interface SessionRecapTrickRow {
  canonicalName: string;
  landed: number;
  missed: number;
  total: number;
}

/** Deterministic session recap built from self-reported attempts (Milestone 1). */
export interface SessionRecap {
  session_id: string;
  started_at: string;
  ended_at: string;
  spot_label: string | null;
  focus_trick: string | null;
  attempts_count: number;
  landed_count: number;
  missed_count: number;
  landed_rate: number | null;
  duration_seconds: number | null;
  trick_breakdown: SessionRecapTrickRow[];
}
