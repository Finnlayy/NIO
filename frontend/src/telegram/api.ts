import { WRITE_HEADER } from "./proxy";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null,
    readonly retryAfterS: number | null,
  ) {
    super(message);
  }
}

async function failure(res: Response): Promise<ApiError> {
  const body = (await res.json().catch(() => null)) as { detail?: unknown; code?: string; retry_after_s?: number } | null;
  const detail = typeof body?.detail === "string" ? body.detail : `Fehler ${res.status}`;
  const code = res.status === 404 && !body?.code ? "not_running" : (body?.code ?? null);
  return new ApiError(detail, res.status, code, body?.retry_after_s ?? null);
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/telegram/${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw await failure(res);
  return (await res.json()) as T;
}

export const get = <T>(path: string): Promise<T> => call<T>(path);

export const post = <T>(path: string, body?: unknown): Promise<T> =>
  call<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", [WRITE_HEADER]: "1" },
    body: JSON.stringify(body ?? {}),
  });

export const del = <T>(path: string): Promise<T> => call<T>(path, { method: "DELETE", headers: { [WRITE_HEADER]: "1" } });
