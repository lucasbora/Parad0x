import type {
  BaselineResponse,
  AllDay,
  BreakEvenOk,
  PackageResponse,
  Change,
  CorridorResponse,
  Profile,
  ScanResponse,
  SimulateResponse,
} from "./types/corridor";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON body */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  corridor: () => request<CorridorResponse>("/api/corridor"),
  baseline: (profile: Profile, demandScale = 1) =>
    request<BaselineResponse>(`/api/corridor/baseline?profile=${profile}&demandScale=${demandScale}`),
  simulate: (changes: Change[], profile: Profile, demandScale = 1, signal?: AbortSignal, evaporation = 0) =>
    request<SimulateResponse>("/api/corridor/simulate", {
      method: "POST",
      body: JSON.stringify({ changes, demandScale, profile, evaporation }),
      signal,
    }),
  breakeven: (changes: Change[], profile: Profile, demandScale = 1, signal?: AbortSignal) =>
    request<BreakEvenOk>("/api/corridor/breakeven", {
      method: "POST",
      body: JSON.stringify({ changes, demandScale, profile }),
      signal,
    }),
  package: (profile: Profile) => request<PackageResponse>(`/api/corridor/package?profile=${profile}`),
  allday: (changes: Change[], profile: Profile, signal?: AbortSignal, evaporation = 0) =>
    request<{ status: "ok"; profiles: AllDay }>("/api/corridor/allday", {
      method: "POST",
      body: JSON.stringify({ changes, profile, evaporation }),
      signal,
    }),
  scan: (profile: Profile) => request<ScanResponse>(`/api/corridor/scan?profile=${profile}`),
};

export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("ro-RO", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Travel time of a street: "45 s" or "1 min 08 s" (a change of a few seconds stays visible). */
export function fmtDuration(sec: number | null | undefined): string {
  if (sec === null || sec === undefined || Number.isNaN(sec)) return "—";
  const s = Math.round(sec);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
}

export function signed(n: number, digits = 1): string {
  if (Math.abs(n) < 0.5 * 10 ** -digits) return fmt(0, digits);
  return `${n > 0 ? "+" : "−"}${fmt(Math.abs(n), digits)}`;
}
