export type ApiErrorKind =
  | "configuration"
  | "network"
  | "timeout"
  | "unauthorized"
  | "client"
  | "server"
  | "malformed";

export interface ApiError {
  kind: ApiErrorKind;
  message: string;
  status?: number;
  detail?: string;
}

export interface ApiSuccess<T> {
  ok: true;
  data: T;
  status: number;
}

export interface ApiFailure {
  ok: false;
  error: ApiError;
}

export type ApiResult<T> = ApiSuccess<T> | ApiFailure;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  headers?: Record<string, string>;
  body?: unknown;
  timeoutMs?: number;
  signal?: AbortSignal;
  /** When true, attach Authorization header from auth provider if available. */
  auth?: boolean;
}

export type HealthResponse = {
  status: string;
  db?: string;
  gemini_configured?: boolean;
  twelvelabs_configured?: boolean;
  clip_review_ready?: boolean;
};

export const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;
