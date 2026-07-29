import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchClipJobMock = vi.fn();

vi.mock("../../api/jobApi", () => ({
  fetchClipJob: (...args: unknown[]) => fetchClipJobMock(...args),
}));

import { pollClipJobUntilDone } from "../../analysis/pollClipJob";

describe("pollClipJobUntilDone", () => {
  beforeEach(() => {
    fetchClipJobMock.mockReset();
  });

  it("returns completed jobs", async () => {
    fetchClipJobMock
      .mockResolvedValueOnce({ ok: true, data: { job_id: "job-1", status: "processing" }, status: 200 })
      .mockResolvedValueOnce({
        ok: true,
        data: {
          job_id: "job-1",
          status: "completed",
          result: {
            clip_label: "Kickflip",
            review_summary: "Clean catch.",
            review_readiness: "usable",
            observations: ["Full rotation"],
            model_confidence_percent: null,
          },
        },
        status: 200,
      });

    const result = await pollClipJobUntilDone("job-1", {
      intervalMs: 1,
      maxIntervalMs: 2,
      timeoutMs: 100,
    });
    expect(result.ok).toBe(true);
    expect(fetchClipJobMock).toHaveBeenCalledTimes(2);
  });

  it("stops immediately on permanent client failures", async () => {
    fetchClipJobMock.mockResolvedValue({
      ok: false,
      error: { kind: "client", message: "Job not found", status: 404 },
    });

    const result = await pollClipJobUntilDone("missing", {
      intervalMs: 1,
      maxIntervalMs: 2,
      timeoutMs: 100,
    });
    expect(result.ok).toBe(false);
    expect(fetchClipJobMock).toHaveBeenCalledOnce();
  });

  it("retries transient failures and then succeeds", async () => {
    fetchClipJobMock
      .mockResolvedValueOnce({ ok: false, error: { kind: "network", message: "offline" } })
      .mockResolvedValueOnce({ ok: true, data: { job_id: "job-1", status: "failed", failure_reason: "bad angle" }, status: 200 });

    const result = await pollClipJobUntilDone("job-1", {
      intervalMs: 1,
      maxIntervalMs: 2,
      timeoutMs: 100,
    });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.status).toBe("failed");
    expect(fetchClipJobMock).toHaveBeenCalledTimes(2);
  });

  it("honors cancellation without issuing another request", async () => {
    const controller = new AbortController();
    controller.abort();
    const result = await pollClipJobUntilDone("job-1", {
      signal: controller.signal,
      intervalMs: 1,
      timeoutMs: 100,
    });
    expect(result.ok).toBe(false);
    expect(fetchClipJobMock).not.toHaveBeenCalled();
  });
});
