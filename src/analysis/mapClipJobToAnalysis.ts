import type { ClipJob } from "../api/types/clipJob";
import type { Analysis, Observation } from "../types";

export const API_ENGINE_VERSION = "onflow-api-v1";

function trickLabelsMatch(called: string, onFilm: string): boolean {
  return called.trim().toLowerCase() === onFilm.trim().toLowerCase();
}

function normalizedReadiness(readiness: string): "detected" | "limited" | "insufficient" {
  const value = readiness.trim().toLowerCase();
  if (["sufficient", "usable", "ready", "detected", "complete"].includes(value)) return "detected";
  if (value === "limited") return "limited";
  return "insufficient";
}

function observationTag(readiness: string): Observation["tag"] {
  const normalized = normalizedReadiness(readiness);
  if (normalized === "insufficient") return "NO EVIDENCE";
  if (normalized === "limited") return "ESTIMATE";
  return "DETECTED";
}

function evidenceClassFromReadiness(readiness: string): Analysis["evidenceClass"] {
  return observationTag(readiness);
}

export function mapClipJobToAnalysis(
  job: Extract<ClipJob, { status: "completed" }>,
  trickCalled: string,
): Analysis {
  const { result } = job;
  const trickOnFilm = result.clip_label.trim() || null;
  const mismatch = trickOnFilm ? !trickLabelsMatch(trickCalled, trickOnFilm) : false;
  const readiness = normalizedReadiness(result.review_readiness);
  const insufficient = readiness === "insufficient";
  const normalized = result.normalized_review;

  const observations: Observation[] = result.observations.slice(0, 8).map((text) => ({
    text,
    tag: observationTag(result.review_readiness),
  }));

  if (observations.length === 0 && result.review_summary.trim()) {
    observations.push({
      text: result.review_summary.trim(),
      tag: observationTag(result.review_readiness),
    });
  }

  const verdict =
    result.skate_clip_review?.verdict?.trim() ||
    normalized?.summary.trim() ||
    result.review_summary.trim() ||
    observations[0]?.text ||
    "No readable review was returned.";

  const workOn =
    result.best_cue?.trim() ||
    result.first_actionable_cue_shown?.trim() ||
    normalized?.what_to_fix[0]?.trim() ||
    normalized?.drill?.trim() ||
    "No specific correction was returned for this clip.";

  return {
    trickCalled,
    trickOnFilm,
    mismatch,
    abstained: insufficient && normalized?.score == null,
    rating: normalized?.score ?? null,
    verdict,
    observations,
    breakdown: result.skate_clip_review?.breakdown ?? null,
    workOn,
    styleNote: normalized?.what_you_did_right[0]?.trim() ?? null,
    source: "user",
    engineVersion: API_ENGINE_VERSION,
    evidenceClass: evidenceClassFromReadiness(result.review_readiness),
    confidence: result.model_confidence_percent,
    receipts: [
      {
        id: "job",
        label: "Analysis job",
        source: "detected",
        detail: job.job_id,
      },
      {
        id: "readiness",
        label: "Review readiness",
        source: "detected",
        detail: result.review_readiness,
      },
    ],
    abstainReason: insufficient ? "The server did not return sufficient evidence for an automated rating." : null,
  };
}
