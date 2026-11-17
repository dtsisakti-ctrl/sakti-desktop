// Thin fetch wrapper around the ExamGuard API (same origin: /api/v1/...).
// The session token and active organization are kept in localStorage (per-browser convenience);
// every call sends `Authorization: Bearer` and, for /org endpoints, `X-Org-Id`.
// Admin Web and Candidate Portal keep separate sessions: each entry point calls useStore() first.

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

let TOKEN = "eg.admin.token";
let ORG = "eg.admin.org";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private mode: the session simply lasts for this tab */
  }
}

let token: string | null = read(TOKEN);
let orgId: string | null = read(ORG);
let onUnauthorized: () => void = () => {};

/** Select the session store before anything else runs: "eg.admin" (default) or "eg.portal". */
export function selectStore(prefix: "eg.admin" | "eg.portal") {
  TOKEN = `${prefix}.token`;
  ORG = `${prefix}.org`;
  token = read(TOKEN);
  orgId = read(ORG);
}

/** Small values that should survive a reload in this browser (e.g. a pending invitation). */
export const local = { read, write };

export const session = {
  get token() {
    return token;
  },
  get orgId() {
    return orgId;
  },
  setToken(v: string | null) {
    token = v;
    write(TOKEN, v);
  },
  setOrg(v: string | null) {
    orgId = v;
    write(ORG, v);
  },
  onUnauthorized(fn: () => void) {
    onUnauthorized = fn;
  },
};

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function request<T>(method: Method, path: string, body?: unknown, raw = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (orgId && path.startsWith("/api/v1/org")) headers["X-Org-Id"] = orgId;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "NETWORK", "network error");
  }
  if (res.status === 401 && !path.includes("/auth/")) {
    onUnauthorized();
  }
  if (!res.ok) {
    let err: { code?: string; message?: string; details?: unknown } = {};
    try {
      err = (await res.json()).error ?? {};
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, err.code ?? `HTTP_${res.status}`, err.message ?? res.statusText, err.details);
  }
  if (raw) return (await res.blob()) as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown = {}) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
  blob: (path: string) => request<Blob>("GET", path, undefined, true),
};

/** /api/v1/org shortcut */
export const org = (path: string) => `/api/v1/org${path}`;
