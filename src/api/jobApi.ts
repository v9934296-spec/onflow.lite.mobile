import { apiRequest } from "./client";
import type { ApiResult } from "./types";
import { parseClipJob, type ClipJob } from "./types/clipJob";

export async function fetchClipJob(jobId: string, signal?: AbortSignal): Promise<ApiResult<ClipJob>> {
  const res = await apiRequest<unknown>(`/api/v1/clips/jobs/${encodeURIComponent(jobId)}`, {
    auth: true,
    signal,
  });
  if (!res.ok) return res;

  const parsed = parseClipJob(res.data);
  if (!parsed) {
    return {
      ok: false,
      error: {
        kind: "malformed",
        message: "Could not parse analysis job from server.",
        status: res.status,
      },
    };
  }
  return { ok: true, data: parsed, status: res.status };
}
