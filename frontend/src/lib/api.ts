import { getCookie } from "./utils";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

type Query = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

export function buildQuery(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => sp.append(key, String(v)));
    else sp.set(key, String(value));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

function messageFrom(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean)
      .join("; ") || fallback;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return fallback;
}

export async function request<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query; form?: FormData; signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    const token = csrfToken ?? getCookie("tuc_csrf");
    if (token) headers["X-CSRF-Token"] = token;
  }
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}${buildQuery(options.query)}`, {
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: options.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? (JSON.parse(text) as unknown) : undefined;
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | undefined)?.detail;
    const err = new ApiError(res.status, messageFrom(detail, res.statusText), detail);
    if (res.status === 401 && !path.startsWith("/auth/")) {
      window.dispatchEvent(new CustomEvent("tuc:unauthorized"));
    }
    throw err;
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) => request<T>("GET", path, { query, signal }),
  post: <T>(path: string, body?: unknown, query?: Query) => request<T>("POST", path, { body, query }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  del: <T = void>(path: string, query?: Query) => request<T>("DELETE", path, { query }),
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, { form }),
};
