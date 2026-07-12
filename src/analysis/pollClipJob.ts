import { fetchClipJob } from "../api/jobApi";
import type { ClipJob, ClipJobStatus } from "../api/types/clipJob";
import type { ApiResult } from "../api/types";

const TERMINAL: ClipJobStatus[] = ["completed", "failed"];

export interface PollClipJobOptions {
  intervalMs?: number;
  timeoutMs?: number;
  onStatus?: (status: ClipJobStatus) => void;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function pollClipJobUntilDone(
  jobId: string,
  options: PollClipJobOptions = {},
): Promise<ApiResult<ClipJob>> {
  const intervalMs = options.intervalMs ?? 2000;
  const timeoutMs = options.timeoutMs ?? 120_000;
  const started = Date.now();
  let lastError: ApiResult<never> | null = null;

  while (Date.now() - started < timeoutMs) {
    const res = await fetchClipJob(jobId);
    if (!res.ok) {
      lastError = res;
      await sleep(intervalMs);
      continue;
    }

    options.onStatus?.(res.data.status);
    if (TERMINAL.includes(res.data.status)) {
      return res;
    }

    await sleep(intervalMs);
  }

  if (lastError) return lastError;
  return {
    ok: false,
    error: {
      kind: "timeout",
      message: "Analysis is taking longer than expected. Try again in a moment.",
    },
  };
}
