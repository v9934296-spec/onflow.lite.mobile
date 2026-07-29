import { fetchClipJob } from "../api/jobApi";
import type { ApiResult } from "../api/types";
import type { ClipJob, ClipJobStatus } from "../api/types/clipJob";

const TERMINAL: ClipJobStatus[] = ["completed", "failed"];

export interface PollClipJobOptions {
  intervalMs?: number;
  maxIntervalMs?: number;
  timeoutMs?: number;
  signal?: AbortSignal;
  onStatus?: (status: ClipJobStatus) => void;
}

function cancelledResult(): ApiResult<never> {
  return { ok: false, error: { kind: "network", message: "Analysis check cancelled." } };
}

function sleep(ms: number, signal?: AbortSignal): Promise<boolean> {
  if (signal?.aborted) return Promise.resolve(false);
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve(true);
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      resolve(false);
    };
    signal?.addEventListener("abort", onAbort);
  });
}

function isRetryableFailure(result: Extract<ApiResult<never>, { ok: false }>): boolean {
  return (
    result.error.kind === "network" ||
    result.error.kind === "timeout" ||
    result.error.kind === "server" ||
    result.error.status === 429
  );
}

export async function pollClipJobUntilDone(
  jobId: string,
  options: PollClipJobOptions = {},
): Promise<ApiResult<ClipJob>> {
  const intervalMs = options.intervalMs ?? 2_000;
  const maxIntervalMs = options.maxIntervalMs ?? 10_000;
  const timeoutMs = options.timeoutMs ?? 180_000;
  const started = Date.now();
  let failureCount = 0;

  while (Date.now() - started < timeoutMs) {
    if (options.signal?.aborted) return cancelledResult();

    const res = await fetchClipJob(jobId, options.signal);
    if (!res.ok) {
      if (options.signal?.aborted) return cancelledResult();
      if (!isRetryableFailure(res)) return res;

      failureCount += 1;
      const backoff = Math.min(maxIntervalMs, intervalMs * 2 ** Math.min(failureCount, 4));
      const jitter = Math.round(backoff * 0.15 * Math.random());
      if (!(await sleep(backoff + jitter, options.signal))) return cancelledResult();
      continue;
    }

    failureCount = 0;
    options.onStatus?.(res.data.status);
    if (TERMINAL.includes(res.data.status)) {
      return res;
    }

    if (!(await sleep(intervalMs, options.signal))) return cancelledResult();
  }

  return {
    ok: false,
    error: {
      kind: "timeout",
      message: "Analysis is still processing. You can leave this screen and resume it from Home.",
    },
  };
}
