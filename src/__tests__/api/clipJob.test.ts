import { describe, expect, it } from "vitest";
import { parseClipJob } from "../../api/types/clipJob";

const COMPLETED_JOB = {
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

describe("parseClipJob", () => {
  it("parses a pending job", () => {
    expect(parseClipJob({ job_id: "j1", status: "pending" })).toEqual({
      job_id: "j1",
      status: "pending",
    });
  });

  it("parses a failed job", () => {
    expect(parseClipJob({ job_id: "j1", status: "failed", failure_reason: "bad clip" })).toEqual({
      job_id: "j1",
      status: "failed",
      failure_reason: "bad clip",
    });
  });

  it("parses a completed job with result", () => {
    const parsed = parseClipJob(COMPLETED_JOB);
    expect(parsed?.status).toBe("completed");
    if (parsed?.status !== "completed") return;
    expect(parsed.result.clip_label).toBe("Kickflip");
    expect(parsed.result.normalized_review?.score).toBe(7.5);
    expect(parsed.result.observations).toHaveLength(2);
  });

  it("unwraps nested data envelope and prefers completed result", () => {
    const parsed = parseClipJob({
      data: { job_id: "j1", status: "processing" },
      job_id: "j1",
      status: "completed",
      result: COMPLETED_JOB.result,
    });
    expect(parsed?.status).toBe("completed");
  });

  it("rejects malformed payloads", () => {
    expect(parseClipJob(null)).toBeNull();
    expect(parseClipJob({ status: "completed" })).toBeNull();
    expect(parseClipJob({ job_id: "j1", status: "failed" })).toBeNull();
  });
});
