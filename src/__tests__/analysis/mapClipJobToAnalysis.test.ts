import { describe, expect, it } from "vitest";
import { mapClipJobToAnalysis, API_ENGINE_VERSION } from "../../analysis/mapClipJobToAnalysis";
import type { ClipJob } from "../../api/types/clipJob";

const COMPLETED: Extract<ClipJob, { status: "completed" }> = {
  job_id: "job-1",
  status: "completed",
  result: {
    clip_label: "Kickflip",
    review_summary: "Clean catch.",
    review_readiness: "usable",
    observations: ["Full rotation", "Solid landing"],
    normalized_review: {
      summary: "Strong kickflip.",
      score: 7.5,
      what_to_fix: ["Pop harder"],
      what_you_did_right: ["Good shoulders"],
      drill: "Pop drills",
    },
    skate_clip_review: {
      verdict: "Clean kickflip.",
      breakdown: [{ k: "Pop", v: 7 }, { k: "Catch", v: 8 }],
    },
  },
};

describe("mapClipJobToAnalysis", () => {
  it("maps a completed API job into Analysis", () => {
    const analysis = mapClipJobToAnalysis(COMPLETED, "Kickflip");
    expect(analysis.trickCalled).toBe("Kickflip");
    expect(analysis.trickOnFilm).toBe("Kickflip");
    expect(analysis.mismatch).toBe(false);
    expect(analysis.rating).toBe(7.5);
    expect(analysis.engineVersion).toBe(API_ENGINE_VERSION);
    expect(analysis.source).toBe("user");
    expect(analysis.observations).toHaveLength(2);
    expect(analysis.breakdown).toHaveLength(2);
  });

  it("flags trick mismatch when clip label differs", () => {
    const analysis = mapClipJobToAnalysis(COMPLETED, "Heelflip");
    expect(analysis.mismatch).toBe(true);
  });

  it("abstains when review readiness is insufficient", () => {
    const job: Extract<ClipJob, { status: "completed" }> = {
      ...COMPLETED,
      result: {
        ...COMPLETED.result,
        review_readiness: "insufficient",
        normalized_review: null,
      },
    };
    const analysis = mapClipJobToAnalysis(job, "Kickflip");
    expect(analysis.abstained).toBe(true);
    expect(analysis.evidenceClass).toBe("NO EVIDENCE");
  });
});
