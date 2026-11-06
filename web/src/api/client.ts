// Client HTTP de l'API : ajoute le jeton, transforme les erreurs, signale les 401.

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

let token: string | null = null;
let onUnauthorized: () => void = () => {};

export function setToken(value: string | null): void {
  token = value;
}

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

function detailMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // Erreurs de validation pydantic : premier message lisible.
    const first = detail[0] as { msg?: string; loc?: unknown[] };
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : undefined;
    return field ? `${String(field)} : ${first.msg}` : (first.msg ?? "Requête invalide.");
  }
  if (status >= 500) return "Erreur du serveur. Réessayez dans un instant.";
  return `Requête refusée (${status}).`;
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "API injoignable. Vérifiez qu'elle est démarrée.");
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // 401 sur une route authentifiée : la session a expiré ou le jeton est invalide.
    if (response.status === 401 && token) onUnauthorized();
    throw new ApiError(response.status, detailMessage(data, response.status));
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  delete: (path: string) => request<void>("DELETE", path),
};
