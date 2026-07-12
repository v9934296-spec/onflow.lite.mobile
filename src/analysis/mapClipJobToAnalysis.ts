import type { ClipJob } from "../api/types/clipJob";
import type { Analysis, Observation } from "../types";

export const API_ENGINE_VERSION = "onflow-api-v1";

function trickLabelsMatch(called: string, onFilm: string): boolean {
  return called.trim().toLowerCase() === onFilm.trim().toLowerCase();
}

function observationTag(readiness: string): Observation["tag"] {
  if (readiness === "insufficient") return "NO EVIDENCE";
  if (readiness === "limited") return "ESTIMATE";
  return "DETECTED";
}

function evidenceClassFromReadiness(readiness: string): Analysis["evidenceClass"] {
  if (readiness === "insufficient") return "NO EVIDENCE";
  if (readiness === "limited") return "ESTIMATE";
  return "DETECTED";
}

export function mapClipJobToAnalysis(
  job: Extract<ClipJob, { status: "completed" }>,
  trickCalled: string,
): Analysis {
  const { result } = job;
  const trickOnFilm = result.clip_label?.trim() || null;
  const mismatch = trickOnFilm ? !trickLabelsMatch(trickCalled, trickOnFilm) : false;
  const insufficient = result.review_readiness === "insufficient";
  const normalized = result.normalized_review;

  const observations: Observation[] = (result.observations ?? []).slice(0, 8).map((text) => ({
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
    normalized?.summary?.trim() ||
    result.review_summary.trim() ||
    "Analysis complete.";

  const workOn =
    result.best_cue?.trim() ||
    result.first_actionable_cue_shown?.trim() ||
    normalized?.what_to_fix[0]?.trim() ||
    normalized?.drill?.trim() ||
    "Review the observations and note what to try next.";

  const rating = normalized?.score ?? null;
  const confidence =
    rating != null ? Math.min(100, Math.round((rating / 10) * 100)) : insufficient ? 0 : 50;

  return {
    trickCalled,
    trickOnFilm,
    mismatch,
    abstained: insufficient && rating === null,
    rating,
    verdict,
    observations,
    breakdown: result.skate_clip_review?.breakdown ?? null,
    workOn,
    styleNote: normalized?.what_you_did_right[0]?.trim() ?? null,
    source: "user",
    engineVersion: API_ENGINE_VERSION,
    evidenceClass: evidenceClassFromReadiness(result.review_readiness),
    confidence,
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
    abstainReason: insufficient ? "Insufficient evidence in clip for automated rating." : null,
  };
}
