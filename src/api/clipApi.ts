import * as FileSystem from "expo-file-system";

import { apiRequest } from "./client";
import type { ApiResult } from "./types";

export const MAX_CLIP_DURATION_SECONDS = 15;
export const MAX_CLIP_SIZE_BYTES = 75 * 1024 * 1024;
export const CLIP_UPLOAD_TIMEOUT_MS = 90_000;

type UploadMethod = "POST" | "PUT" | "PATCH";

export interface InitiateClipUploadResponse {
  clip_id: string;
  upload_url: string;
  upload_method: UploadMethod;
  upload_expires_at: string;
  storage_key: string;
}

export interface UploadClipParams {
  sessionId: string;
  fileUri: string;
  mimeType: string;
  durationSeconds: number;
  widthPx: number;
  heightPx: number;
  sizeBytes: number;
  clientHintTrickId?: string | null;
  onProgress?: (fraction: number) => void;
}

function parseUploadMethod(value: unknown): UploadMethod | null {
  if (typeof value !== "string") return null;
  const method = value.trim().toUpperCase();
  return method === "POST" || method === "PUT" || method === "PATCH" ? method : null;
}

function parseInitiateResponse(raw: unknown): InitiateClipUploadResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const clipId = typeof o.clip_id === "string" ? o.clip_id.trim() : "";
  const uploadUrl = typeof o.upload_url === "string" ? o.upload_url.trim() : "";
  const storageKey = typeof o.storage_key === "string" ? o.storage_key.trim() : "";
  const uploadExpiresAt = typeof o.upload_expires_at === "string" ? o.upload_expires_at.trim() : "";
  const uploadMethod = parseUploadMethod(o.upload_method);
  if (!clipId || !uploadUrl || !storageKey || !uploadExpiresAt || !uploadMethod) return null;
  return {
    clip_id: clipId,
    upload_url: uploadUrl,
    upload_method: uploadMethod,
    upload_expires_at: uploadExpiresAt,
    storage_key: storageKey,
  };
}

export async function initiateSessionClipUpload(params: {
  sessionId: string;
  durationSeconds: number;
  widthPx: number;
  heightPx: number;
  contentType: "video/mp4" | "video/quicktime";
  sizeBytes: number;
  clientHintTrickId?: string | null;
}): Promise<ApiResult<InitiateClipUploadResponse>> {
  const body: Record<string, unknown> = {
    session_id: params.sessionId,
    duration_seconds: params.durationSeconds,
    width_px: params.widthPx,
    height_px: params.heightPx,
    content_type: params.contentType,
    size_bytes: params.sizeBytes,
  };
  if (params.clientHintTrickId?.trim()) {
    body.client_hint_trick_id = params.clientHintTrickId.trim();
  }

  const res = await apiRequest<unknown>("/api/v1/clips/initiate-upload", {
    method: "POST",
    auth: true,
    body,
  });
  if (!res.ok) return res;

  const parsed = parseInitiateResponse(res.data);
  if (!parsed) {
    return {
      ok: false,
      error: { kind: "malformed", message: "Initiate-upload response missing required fields." },
    };
  }
  return { ok: true, data: parsed, status: res.status };
}

export async function uploadClipToPresignedUrl(
  uploadUrl: string,
  uploadMethod: UploadMethod,
  fileUri: string,
  mimeType: string,
  onProgress?: (fraction: number) => void,
): Promise<ApiResult<void>> {
  if (uploadUrl.startsWith("local://")) {
    onProgress?.(1);
    return { ok: true, data: undefined, status: 200 };
  }

  const task = FileSystem.createUploadTask(
    uploadUrl,
    fileUri,
    {
      httpMethod: uploadMethod,
      uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
      headers: { "Content-Type": mimeType },
      sessionType: FileSystem.FileSystemSessionType.FOREGROUND,
    },
    (progress) => {
      const expected = progress.totalBytesExpectedToSend;
      if (expected > 0) {
        onProgress?.(Math.min(1, Math.max(0, progress.totalBytesSent / expected)));
      }
    },
  );

  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  try {
    const result = await Promise.race([
      task.uploadAsync(),
      new Promise<undefined>((resolve) => {
        timeoutId = setTimeout(() => {
          void task.cancelAsync().finally(() => resolve(undefined));
        }, CLIP_UPLOAD_TIMEOUT_MS);
      }),
    ]);

    if (!result) {
      return {
        ok: false,
        error: {
          kind: "timeout",
          message: "Clip upload timed out. Check your connection and try again.",
        },
      };
    }

    if (result.status < 200 || result.status >= 300) {
      return {
        ok: false,
        error: {
          kind: result.status >= 500 ? "server" : "client",
          message: `Storage upload failed (${result.status}).`,
          status: result.status,
        },
      };
    }

    onProgress?.(1);
    return { ok: true, data: undefined, status: result.status };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed.";
    return { ok: false, error: { kind: "network", message } };
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

export async function completeSessionClipUpload(clipId: string): Promise<ApiResult<void>> {
  const res = await apiRequest<unknown>(`/api/v1/clips/${encodeURIComponent(clipId)}/complete-upload`, {
    method: "POST",
    auth: true,
  });
  if (!res.ok) {
    if (res.error.status === 409) {
      return { ok: true, data: undefined, status: 409 };
    }
    return res;
  }
  return { ok: true, data: undefined, status: res.status };
}

/** Initiate → native binary upload → complete-upload. Returns the analysis job id. */
export async function uploadClipToSession(params: UploadClipParams): Promise<ApiResult<string>> {
  if (params.durationSeconds <= 0 || params.durationSeconds > MAX_CLIP_DURATION_SECONDS) {
    return {
      ok: false,
      error: {
        kind: "client",
        message: `Clips must be ${MAX_CLIP_DURATION_SECONDS} seconds or shorter.`,
      },
    };
  }
  if (params.sizeBytes <= 0 || params.sizeBytes > MAX_CLIP_SIZE_BYTES) {
    return {
      ok: false,
      error: {
        kind: "client",
        message: "Clip is too large. Choose a video under 75 MB.",
      },
    };
  }

  const contentType: "video/mp4" | "video/quicktime" =
    params.mimeType === "video/quicktime" ? "video/quicktime" : "video/mp4";

  const initiated = await initiateSessionClipUpload({
    sessionId: params.sessionId,
    durationSeconds: params.durationSeconds,
    widthPx: params.widthPx,
    heightPx: params.heightPx,
    contentType,
    sizeBytes: params.sizeBytes,
    clientHintTrickId: params.clientHintTrickId,
  });
  if (!initiated.ok) return initiated;

  const expiresAt = Date.parse(initiated.data.upload_expires_at);
  if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
    return {
      ok: false,
      error: { kind: "client", message: "Upload authorization expired. Please try again." },
    };
  }

  const uploaded = await uploadClipToPresignedUrl(
    initiated.data.upload_url,
    initiated.data.upload_method,
    params.fileUri,
    params.mimeType,
    params.onProgress,
  );
  if (!uploaded.ok) return uploaded;

  const completed = await completeSessionClipUpload(initiated.data.clip_id);
  if (!completed.ok) return completed;

  return { ok: true, data: initiated.data.clip_id, status: completed.status };
}
