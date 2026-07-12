import { buildAuthHeaders, notifyAuthExpiredOn401 } from "./auth";
import { getApiBaseUrl } from "./baseUrl";
import { isExpoApiUrlConfigured } from "./config";
import {
  configurationFailureMessage,
  extractApiErrorBody,
  isAbortError,
  isNetworkFetchError,
  networkFailureHint,
} from "./errors";
import { mergeApiTelemetryHeaders } from "./telemetry";
import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  type ApiError,
  type ApiErrorKind,
  type ApiResult,
  type RequestOptions,
} from "./types";

export async function safeReadJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text.trim()) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { _nonJson: text.slice(0, 200) };
  }
}

function failure(kind: ApiErrorKind, message: string, status?: number, detail?: string): ApiResult<never> {
  return { ok: false, error: { kind, message, status, detail } };
}

function classifyHttpError(status: number, body: unknown): ApiError {
  const detail = extractApiErrorBody(body) ?? undefined;
  if (status === 401) {
    return {
      kind: "unauthorized",
      message: detail ?? "Session expired or not authorized.",
      status,
      detail,
    };
  }
  if (status >= 500) {
    return {
      kind: "server",
      message: detail ?? `Server error (${status}).`,
      status,
      detail,
    };
  }
  if (status >= 400) {
    return {
      kind: "client",
      message: detail ?? `Request failed (${status}).`,
      status,
      detail,
    };
  }
  return {
    kind: "malformed",
    message: `Unexpected response status (${status}).`,
    status,
    detail,
  };
}

function devLog(method: string, url: string, status: number): void {
  if (typeof __DEV__ !== "undefined" && __DEV__) {
    console.info(`[api] ${method} ${url} → ${status}`);
  }
}

/** Centralized fetch wrapper. Returns ApiResult — never throws for HTTP/network errors. */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  if (!isExpoApiUrlConfigured()) {
    return failure("configuration", configurationFailureMessage());
  }
  if (options.signal?.aborted) {
    return failure("network", "Request cancelled.");
  }

  const base = getApiBaseUrl();
  const url = path.startsWith("http")
    ? path
    : `${base.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
  const method = options.method ?? "GET";
  const timeoutMs = options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...mergeApiTelemetryHeaders({}),
    ...options.headers,
  };

  if (options.auth) {
    const authHeaders = await buildAuthHeaders();
    if (!authHeaders) {
      return failure("unauthorized", "Not signed in.");
    }
    Object.assign(headers, authHeaders);
  }

  let body: string | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort();
  options.signal?.addEventListener("abort", abortFromCaller);
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, { method, headers, body, signal: controller.signal });
  } catch (error) {
    if (isAbortError(error)) {
      return timedOut
        ? failure("timeout", `Request timed out after ${timeoutMs}ms.`)
        : failure("network", "Request cancelled.");
    }
    if (isNetworkFetchError(error)) {
      return failure("network", networkFailureHint(base));
    }
    const message = error instanceof Error ? error.message : "Request failed.";
    return failure("network", message);
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }

  notifyAuthExpiredOn401(res);
  devLog(method, url, res.status);

  const raw = await safeReadJson(res);

  if (!res.ok) {
    const err = classifyHttpError(res.status, raw);
    return { ok: false, error: err };
  }

  if (raw !== null && typeof raw === "object" && "_nonJson" in (raw as object)) {
    return failure("malformed", "Server returned a non-JSON response.");
  }

  return { ok: true, data: raw as T, status: res.status };
}
