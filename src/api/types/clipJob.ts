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
  if (st === "completed" && c.result != null && typeof c.result === "object") return 100;
  if (st === "failed") {
    const fr = c.failure_reason ?? c.failureReason;
    return typeof fr === "string" && fr.trim() ? 80 : 15;
  }
  if (st === "processing" || st === "pending") return 60;
  if (st === "completed") return 20;
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
  return v.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function parseScore(v: unknown): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  if (v < 0 || v > 10) return null;
  return v;
}

function parseNormalizedReview(raw: unknown): ClipJobNormalizedReview | null {
  if (!isRecord(raw)) return null;
  const summary = typeof raw.summary === "string" ? raw.summary.trim() : "";
  if (!summary) return null;
  return {
    summary,
    score: parseScore(raw.score),
    what_to_fix: stringArray(raw.what_to_fix ?? raw.whatToFix),
    what_you_did_right: stringArray(raw.what_you_did_right ?? raw.whatYouDidRight),
    drill: typeof raw.drill === "string" && raw.drill.trim() ? raw.drill.trim() : null,
  };
}

function parseBreakdown(raw: unknown): { k: string; v: number }[] | null {
  if (!Array.isArray(raw)) return null;
  const items: { k: string; v: number }[] = [];
  for (const row of raw) {
    if (!isRecord(row)) continue;
    const k = typeof row.k === "string" ? row.k : typeof row.label === "string" ? row.label : null;
    const v = typeof row.v === "number" ? row.v : typeof row.score === "number" ? row.score : null;
    if (k && v != null && Number.isFinite(v)) items.push({ k, v });
  }
  return items.length ? items : null;
}

function parseClipJobResult(raw: unknown, clipLabelFallback: string): ClipJobResult {
  if (!isRecord(raw)) {
    return {
      clip_label: clipLabelFallback,
      review_summary: "Analysis completed but the result could not be read.",
      review_readiness: "insufficient",
      observations: [],
    };
  }

  const clip_label =
    typeof raw.clip_label === "string" && raw.clip_label.trim()
      ? raw.clip_label.trim()
      : typeof raw.clipLabel === "string" && raw.clipLabel.trim()
        ? raw.clipLabel.trim()
        : clipLabelFallback;

  const review_summary =
    typeof raw.review_summary === "string"
      ? raw.review_summary
      : typeof raw.reviewSummary === "string"
        ? raw.reviewSummary
        : "Analysis complete.";

  const review_readiness =
    typeof raw.review_readiness === "string"
      ? raw.review_readiness
      : typeof raw.reviewReadiness === "string"
        ? raw.reviewReadiness
        : "limited";

  const skateRaw = raw.skate_clip_review ?? raw.skateClipReview;
  let skate_clip_review: ClipJobResult["skate_clip_review"] = null;
  if (isRecord(skateRaw)) {
    skate_clip_review = {
      verdict: typeof skateRaw.verdict === "string" ? skateRaw.verdict : null,
      breakdown: parseBreakdown(skateRaw.breakdown),
    };
  }

  return {
    clip_label,
    review_summary,
    review_readiness,
    observations: stringArray(raw.observations),
    normalized_review: parseNormalizedReview(raw.normalized_review ?? raw.normalizedReview),
    best_cue: typeof raw.best_cue === "string" ? raw.best_cue : typeof raw.bestCue === "string" ? raw.bestCue : null,
    first_actionable_cue_shown:
      typeof raw.first_actionable_cue_shown === "string"
        ? raw.first_actionable_cue_shown
        : typeof raw.firstActionableCueShown === "string"
          ? raw.firstActionableCueShown
          : null,
    skate_clip_review,
  };
}

/** Parse GET /api/v1/clips/jobs/{id} (and common envelope shapes). */
export function parseClipJob(json: unknown): ClipJob | null {
  const root = extractJobPayload(json);
  if (!root) return null;

  const job_id = jobIdFromRecord(root);
  const status = normalizeStatus(root.status);
  if (!job_id || !status) return null;

  if (status === "pending" || status === "processing") {
    return { job_id, status };
  }

  if (status === "failed") {
    const fr = root.failure_reason ?? root.failureReason;
    if (typeof fr !== "string" || !fr.trim()) return null;
    return { job_id, status: "failed", failure_reason: fr.trim() };
  }

  let resultRaw: unknown = root.result;
  if (typeof resultRaw === "string") {
    try {
      resultRaw = JSON.parse(resultRaw) as unknown;
    } catch {
      resultRaw = null;
    }
  }

  const hinted =
    isRecord(resultRaw) && typeof resultRaw.clip_label === "string"
      ? resultRaw.clip_label
      : isRecord(resultRaw) && typeof resultRaw.clipLabel === "string"
        ? resultRaw.clipLabel
        : "untagged";

  return {
    job_id,
    status: "completed",
    result: parseClipJobResult(resultRaw, hinted),
  };
}
