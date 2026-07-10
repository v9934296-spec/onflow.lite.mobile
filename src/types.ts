export type EvidenceTag = "DETECTED" | "ESTIMATE" | "NO EVIDENCE";

export interface Observation {
  text: string;
  tag: EvidenceTag;
}

export interface BreakdownItem {
  k: string; // component name, e.g. "Pop"
  v: number; // 0–10
}

export interface Analysis {
  trickCalled: string;
  trickOnFilm: string | null; // null when the engine can't see the footage
  mismatch: boolean;
  abstained: boolean;
  rating: number | null; // null when abstained
  verdict: string;
  observations: Observation[];
  breakdown: BreakdownItem[] | null;
  workOn: string;
  styleNote: string | null;
  source: "sample" | "user"; // sample = scripted lite clip, user = their own footage
}

export interface SampleClip {
  id: string;
  label: string;
  canonical: string; // the trick actually on film
  spot: string;
  durationSec: number;
}

export interface LoggedClip {
  id: string;
  loggedAt: string; // ISO
  analysis: Analysis;
}
