/**
 * Typed API client for the ResearchOS backend.
 *
 * All requests send credentials (the session cookie). Mutating requests
 * automatically attach the double-submit CSRF token read from the `ros_csrf`
 * cookie (see backend PHASE1_DECISIONS P1-D3).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

const CSRF_COOKIE = 'ros_csrf';
const CSRF_HEADER = 'X-CSRF-Token';

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details?: Record<string, unknown>;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string | null;

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.error?.message ?? fallback);
    this.name = 'ApiError';
    this.status = status;
    this.code = body?.error?.code ?? 'unknown_error';
    this.requestId = body?.error?.request_id ?? null;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

interface RequestOptions {
  method?: Method;
  body?: unknown;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (method !== 'GET') {
    const token = readCookie(CSRF_COOKIE);
    if (token) headers[CSRF_HEADER] = token;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  if (!res.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      body = null;
    }
    throw new ApiError(res.status, body, `Request failed with status ${res.status}`);
  }

  return (await res.json()) as T;
}

// --- Health endpoints (used by the system status panel) ----------------------

export interface DependencyCheck {
  name: string;
  status: 'ok' | 'error';
  detail: string | null;
}

export interface ReadinessResponse {
  status: 'ok' | 'error';
  checks: DependencyCheck[];
}

export function getReadiness(): Promise<ReadinessResponse> {
  return apiRequest<ReadinessResponse>('/readyz');
}
