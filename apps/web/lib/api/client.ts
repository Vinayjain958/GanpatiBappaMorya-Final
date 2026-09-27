import { env } from "@/lib/config/env";
import { getAccessToken, setAccessToken } from "@/lib/auth/tokenStore";

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface FastApiValidationError {
  loc?: unknown[];
  msg?: string;
}

/** FastAPI/Pydantic 422 bodies carry a generic top-level "message" (e.g.
 * "Validation failed") with the real per-field reasons in `detail`. Turn
 * those into one readable sentence instead of showing the generic string
 * or a raw Pydantic error dump. */
function describeValidationError(detail: unknown): string | null {
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const messages = (detail as FastApiValidationError[])
    .map((item) => {
      const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : undefined;
      const label = typeof field === "string" ? fieldLabels[field] ?? field : null;
      return label && item.msg ? `${label}: ${item.msg}` : item.msg;
    })
    .filter((message): message is string => Boolean(message));
  return messages.length ? messages.join(" ") : null;
}

const fieldLabels: Record<string, string> = {
  email: "Email",
  password: "Password",
  display_name: "Full name",
  business_name: "Business name",
  role: "Account type",
};

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  /** Internal — set on the retry attempt after a refresh to avoid infinite loops. */
  _isRetry?: boolean;
}

interface FormRequestOptions {
  signal?: AbortSignal;
  headers?: Record<string, string>;
  _isRetry?: boolean;
}

// Endpoints that must never trigger the automatic refresh-and-retry
// dance — refresh itself, and the two endpoints that establish/replace
// a session from scratch (a 401 there is a real, final answer).
const NO_REFRESH_RETRY_PATHS = [
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/refresh",
];

/**
 * Central typed API client. All frontend/backend communication goes
 * through this module — components and hooks never call fetch() directly.
 *
 * Auth behavior (Phase 3): every request sends credentials (so the
 * HttpOnly refresh cookie travels on same-origin/CORS-credentialed
 * requests to /api/v1/auth/*) and, when an access token is held in
 * memory (see lib/auth/tokenStore.ts), an `Authorization: Bearer` header.
 * A 401 on any other endpoint triggers exactly one refresh attempt,
 * shared across concurrent callers, followed by one retry of the
 * original request — never an unbounded retry loop.
 */
let refreshPromise: Promise<boolean> | null = null;

// The free-tier backend sleeps when idle and takes up to ~a minute to wake;
// meanwhile the proxy answers 502/503/504 (or the connection drops). Safe
// requests — reads plus login/refresh — are retried with backoff instead of
// surfacing that as an error. Other writes are never retried automatically.
const WAKE_RETRY_STATUSES = new Set([502, 503, 504]);
const WAKE_RETRY_DELAYS_MS = [2000, 4000, 8000, 15000, 20000];
const WAKE_RETRY_SAFE_POSTS = ["/api/v1/auth/login", "/api/v1/auth/refresh"];

function isWakeRetryable(method: string, path: string): boolean {
  return method === "GET" || WAKE_RETRY_SAFE_POSTS.some((p) => path.startsWith(p));
}

function sleep(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(signal.reason);
    }, { once: true });
  });
}

async function fetchWithWakeRetry(path: string, init: RequestInit): Promise<Response> {
  const url = `${env.apiBaseUrl}${path}`;
  const retryable = isWakeRetryable(init.method ?? "GET", path);
  for (let attempt = 0; ; attempt++) {
    const canRetry = retryable && attempt < WAKE_RETRY_DELAYS_MS.length;
    try {
      const response = await fetch(url, init);
      if (!canRetry || !WAKE_RETRY_STATUSES.has(response.status)) return response;
    } catch (cause) {
      if (!canRetry || init.signal?.aborted) throw cause;
    }
    await sleep(WAKE_RETRY_DELAYS_MS[attempt], init.signal);
  }
}

async function attemptRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const response = await fetchWithWakeRetry("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        setAccessToken(null);
        return false;
      }
      const payload = (await response.json()) as { access_token?: string };
      if (!payload.access_token) {
        setAccessToken(null);
        return false;
      }
      setAccessToken(payload.access_token);
      return true;
    } catch {
      setAccessToken(null);
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function request<TResponse>(
  path: string,
  { method = "GET", body, signal, headers, _isRetry = false }: RequestOptions = {},
): Promise<TResponse> {
  const token = getAccessToken();

  let response: Response;
  try {
    response = await fetchWithWakeRetry(path, {
      method,
      signal,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    throw new ApiError("Network request failed", 0, cause);
  }

  return finishResponse(
    response,
    path,
    () => request<TResponse>(path, { method, body, signal, headers, _isRetry: true }),
    _isRetry,
  );
}

/**
 * multipart/form-data POST — used where a file travels alongside form
 * fields (the traveler "Add a Local Experience" upload). Never sets
 * Content-Type itself: the browser must generate it, with the multipart
 * boundary, from the FormData body. Not wake-retried (it's a write), but
 * shares request()'s auth header, 401-refresh-retry and ApiError parsing.
 */
async function requestForm<TResponse>(
  path: string,
  form: FormData,
  { signal, headers, _isRetry = false }: FormRequestOptions = {},
): Promise<TResponse> {
  const token = getAccessToken();

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method: "POST",
      signal,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: form,
    });
  } catch (cause) {
    throw new ApiError("Network request failed", 0, cause);
  }

  return finishResponse(
    response,
    path,
    () => requestForm<TResponse>(path, form, { signal, headers, _isRetry: true }),
    _isRetry,
  );
}

/** Shared 401-refresh-retry and error-parsing tail for request() and
 * requestForm(), so that behavior only ever has to change in one place. */
async function finishResponse<TResponse>(
  response: Response,
  path: string,
  retry: () => Promise<TResponse>,
  isRetry: boolean,
): Promise<TResponse> {
  if (response.status === 401 && !isRetry && !NO_REFRESH_RETRY_PATHS.some((p) => path.startsWith(p))) {
    const refreshed = await attemptRefresh();
    if (refreshed) return retry();
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => undefined)
    : undefined;

  if (!response.ok) {
    const detail = typeof payload === "object" && payload && "detail" in payload
      ? (payload as { detail?: unknown }).detail
      : undefined;
    const validationMessage = response.status === 422 ? describeValidationError(detail) : null;

    throw new ApiError(
      validationMessage
        ?? (typeof payload === "object" && payload && "message" in payload
          ? String((payload as { message?: unknown }).message)
          : `Request failed with status ${response.status}`),
      response.status,
      payload,
    );
  }

  return payload as TResponse;
}

export const apiClient = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "DELETE" }),
  postForm: <T>(path: string, form: FormData, options?: Omit<FormRequestOptions, "_isRetry">) =>
    requestForm<T>(path, form, options),
};
