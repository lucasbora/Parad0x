import type {
  DecidemBriefResponse,
  HealthResponse,
  NetworkResponse,
  Preset,
  SimulateRequest,
  SimulateResponse,
  StreetSearchResult,
} from "../types/simulator";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    signal,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>("/api/health", undefined, signal),
  network: (preset: Preset, signal?: AbortSignal) =>
    request<NetworkResponse>(`/api/network?preset=${preset}`, undefined, signal),
  simulate: (body: SimulateRequest, signal?: AbortSignal) =>
    request<SimulateResponse>("/api/simulate", { method: "POST", body: JSON.stringify(body) }, signal),
  decidemBrief: (body: SimulateRequest) =>
    request<DecidemBriefResponse>("/api/decidem-brief", { method: "POST", body: JSON.stringify(body) }),
  searchStreets: (q: string, signal?: AbortSignal) =>
    request<{ results: StreetSearchResult[] }>(`/api/streets/search?q=${encodeURIComponent(q)}`, undefined, signal),
};
