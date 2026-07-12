export type ClipJobStatus = "pending" | "processing" | "completed" | "failed";

export interface ClipJobNormalizedReview {
  summary: string;
  score: number | null;
  what_to_fix: string[];
  what_you_did_right: string[];
  drill: string | null;
}

export interface ClipJobResult {
  clip_label: string;
  review_summary: string;
  review_readiness: string;
  observations: string[];
  model_confidence_percent: number | null;
  normalized_review?: ClipJobNormalizedReview | null;
  best_cue?: string | null;
  first_actionable_cue_shown?: string | null;
  skate_clip_review?: {
    verdict?: string | null;
    breakdown?: { k: string; v: number }[] | null;
  } | null;
}

export type ClipJob =
  | { job_id: string; status: "pending" | "processing" }
  | { job_id: string; status: "failed"; failure_reason: string }
  | { job_id: string; status: "completed"; result: ClipJobResult };

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function normalizeJobId(v: unknown): string | null {
  if (typeof v === "string" && v.trim()) return v.trim();
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  return null;
}

function jobIdFromRecord(r: Record<string, unknown>): string | null {
  return normalizeJobId(r.job_id ?? r.jobId ?? r.id);
}

function normalizeStatus(v: unknown): ClipJobStatus | null {
  if (typeof v !== "string") return null;
  const s = v.trim().toLowerCase();
  if (s === "done" || s === "complete") return "completed";
  if (s === "pending" || s === "processing" || s === "completed" || s === "failed") return s;
  return null;
}

function looksLikeJobEnvelope(r: Record<string, unknown>): boolean {
  return Boolean(jobIdFromRecord(r) && normalizeStatus(r.status));
}

function collectJobCandidates(json: Record<string, unknown>): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  if (looksLikeJobEnvelope(json)) out.push(json);
  for (const key of ["data", "body", "payload", "job"] as const) {
    const inner = json[key];
    if (isRecord(inner) && looksLikeJobEnvelope(inner)) out.push(inner);
  }
  return out;
}

function rankJobCandidate(c: Record<string, unknown>): number {
  const st = normalizeStatus(c.status);
  if (!st) return -1;
  if (st === "completed" && c.result != null) return 100;
  if (st === "failed") {
    const fr = c.failure_reason ?? c.failureReason;
    return typeof fr === "string" && fr.trim() ? 80 : 15;
  }
  if (st === "processing" || st === "pending") return 60;
  return 0;
}

function extractJobPayload(json: unknown): Record<string, unknown> | null {
  if (!isRecord(json)) return null;
  const candidates = collectJobCandidates(json);
  if (!candidates.length) return null;
  let best = candidates[0];
  let bestRank = rankJobCandidate(best);
  for (let i = 1; i < candidates.length; i += 1) {
    const rank = rankJobCandidate(candidates[i]);
    if (rank > bestRank) {
      best = candidates[i];
      bestRank = rank;
    }
  }
  return best;
}

function stringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

function optionalString(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

function parseScore(v: unknown): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  if (v < 0 || v > 10) return null;
  return v;
}

function parseConfidencePercent(v: unknown): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  if (v < 0 || v > 100) return null;
  return v;
}

function parseNormalizedReview(raw: unknown): ClipJobNormalizedReview | null {
  if (!isRecord(raw)) return null;
  const summary = optionalString(raw.summary);
  if (!summary) return null;
  return {
    summary,
    score: parseScore(raw.score),
    what_to_fix: stringArray(raw.what_to_fix ?? raw.whatToFix),
    what_you_did_right: stringArray(raw.what_you_did_right ?? raw.whatYouDidRight),
    drill: optionalString(raw.drill),
  };
}

function parseBreakdown(raw: unknown): { k: string; v: number }[] | null {
  if (!Array.isArray(raw)) return null;
  const items: { k: string; v: number }[] = [];
  for (const row of raw) {
    if (!isRecord(row)) continue;
    const k = optionalString(row.k ?? row.label);
    const v = typeof row.v === "number" ? row.v : typeof row.score === "number" ? row.score : null;
    if (k && v != null && Number.isFinite(v)) items.push({ k, v });
  }
  return items.length ? items : null;
}

function parseClipJobResult(raw: unknown): ClipJobResult | null {
  if (!isRecord(raw)) return null;

  const clipLabel = optionalString(raw.clip_label ?? raw.clipLabel) ?? "";
  const reviewSummary = optionalString(raw.review_summary ?? raw.reviewSummary) ?? "";
  const reviewReadiness = optionalString(raw.review_readiness ?? raw.reviewReadiness);
  if (!reviewReadiness) return null;

  const normalizedReview = parseNormalizedReview(raw.normalized_review ?? raw.normalizedReview);
  const skateRaw = raw.skate_clip_review ?? raw.skateClipReview;
  let skateClipReview: ClipJobResult["skate_clip_review"] = null;
  if (isRecord(skateRaw)) {
    skateClipReview = {
      verdict: optionalString(skateRaw.verdict),
      breakdown: parseBreakdown(skateRaw.breakdown),
    };
  }

  const observations = stringArray(raw.observations);
  const hasReviewContent = Boolean(
    reviewSummary ||
      normalizedReview?.summary ||
      skateClipReview?.verdict ||
      observations.length > 0,
  );
  if (!hasReviewContent) return null;

  return {
    clip_label: clipLabel,
    review_summary: reviewSummary,
    review_readiness: reviewReadiness,
    observations,
    model_confidence_percent: parseConfidencePercent(
      raw.model_confidence_percent ?? raw.modelConfidencePercent ?? raw.confidence_percent,
    ),
    normalized_review: normalizedReview,
    best_cue: optionalString(raw.best_cue ?? raw.bestCue),
    first_actionable_cue_shown: optionalString(
      raw.first_actionable_cue_shown ?? raw.firstActionableCueShown,
    ),
    skate_clip_review: skateClipReview,
  };
}

/** Parse GET /api/v1/clips/jobs/{id} (and common envelope shapes). */
export function parseClipJob(json: unknown): ClipJob | null {
  const root = extractJobPayload(json);
  if (!root) return null;

  const jobId = jobIdFromRecord(root);
  const status = normalizeStatus(root.status);
  if (!jobId || !status) return null;

  if (status === "pending" || status === "processing") {
    return { job_id: jobId, status };
  }

  if (status === "failed") {
    const failureReason = optionalString(root.failure_reason ?? root.failureReason);
    if (!failureReason) return null;
    return { job_id: jobId, status: "failed", failure_reason: failureReason };
  }

  let resultRaw: unknown = root.result;
  if (typeof resultRaw === "string") {
    try {
      resultRaw = JSON.parse(resultRaw) as unknown;
    } catch {
      return null;
    }
  }

  const result = parseClipJobResult(resultRaw);
  if (!result) return null;
  return { job_id: jobId, status: "completed", result };
}
