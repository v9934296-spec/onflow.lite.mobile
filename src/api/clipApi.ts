import * as FileSystem from "expo-file-system";
import { Platform } from "react-native";
import { apiRequest } from "./client";
import type { ApiResult } from "./types";

function storageUploadFailureMessage(status: number): string {
  if (status === 401 || status === 403) {
    return (
      `Clip storage rejected the upload (${status}). ` +
      "This is the video host (R2/S3), not your OnFlow login — check API R2 credentials and redeploy."
    );
  }
  return `Storage upload failed (${status}).`;
}

export interface InitiateClipUploadResponse {
  clip_id: string;
  upload_url: string;
  upload_method: string;
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
}

function parseInitiateResponse(raw: unknown): InitiateClipUploadResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const clipId = typeof o.clip_id === "string" ? o.clip_id : null;
  const uploadUrl = typeof o.upload_url === "string" ? o.upload_url : null;
  const storageKey = typeof o.storage_key === "string" ? o.storage_key : null;
  const uploadExpiresAt =
    typeof o.upload_expires_at === "string" ? o.upload_expires_at : new Date().toISOString();
  if (!clipId || !uploadUrl || !storageKey) return null;
  return {
    clip_id: clipId,
    upload_url: uploadUrl,
    upload_method: typeof o.upload_method === "string" ? o.upload_method : "PUT",
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
    return { ok: false, error: { kind: "malformed", message: "Initiate-upload response missing required fields." } };
  }
  return { ok: true, data: parsed, status: res.status };
}

export async function uploadClipToPresignedUrl(
  uploadUrl: string,
  fileUri: string,
  mimeType: string,
): Promise<ApiResult<void>> {
  if (uploadUrl.startsWith("local://")) {
    return { ok: true, data: undefined, status: 200 };
  }

  // Native: stream the file URI directly. fetch(fileUri)+blob PUT is unreliable on
  // device and often breaks R2/S3 signature checks (401/403).
  if (Platform.OS !== "web") {
    try {
      const result = await FileSystem.uploadAsync(uploadUrl, fileUri, {
        httpMethod: "PUT",
        uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
        headers: { "Content-Type": mimeType },
      });
      if (result.status < 200 || result.status >= 300) {
        return {
          ok: false,
          error: {
            kind: "server",
            message: storageUploadFailureMessage(result.status),
            status: result.status,
          },
        };
      }
      return { ok: true, data: undefined, status: result.status };
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed.";
      return { ok: false, error: { kind: "network", message } };
    }
  }

  let body: Blob;
  try {
    const fileRes = await fetch(fileUri);
    body = await fileRes.blob();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not read the video file.";
    return { ok: false, error: { kind: "network", message } };
  }

  let res: Response;
  try {
    res = await fetch(uploadUrl, {
      method: "PUT",
      headers: { "Content-Type": mimeType },
      body,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed.";
    return { ok: false, error: { kind: "network", message } };
  }

  if (!res.ok) {
    return {
      ok: false,
      error: {
        kind: "server",
        message: storageUploadFailureMessage(res.status),
        status: res.status,
      },
    };
  }
  return { ok: true, data: undefined, status: res.status };
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

/** Initiate → presigned PUT → complete-upload. Returns clip id (job id in v1 pipeline). */
export async function uploadClipToSession(params: UploadClipParams): Promise<ApiResult<string>> {
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

  const uploaded = await uploadClipToPresignedUrl(
    initiated.data.upload_url,
    params.fileUri,
    params.mimeType,
  );
  if (!uploaded.ok) return uploaded;

  const completed = await completeSessionClipUpload(initiated.data.clip_id);
  if (!completed.ok) return completed;

  return { ok: true, data: initiated.data.clip_id, status: completed.status };
}
