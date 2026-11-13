import type {
  BaselineResponse,
  CalibrationResponse,
  Change,
  CorridorResponse,
  SensitivityResponse,
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
  baseline: (testData: boolean) => request<BaselineResponse>(`/api/corridor/baseline?testData=${testData}`),
  simulate: (changes: Change[], testData: boolean, signal?: AbortSignal) =>
    request<SimulateResponse>("/api/corridor/simulate", {
      method: "POST",
      body: JSON.stringify({ changes, demandScale: 1, testData }),
      signal,
    }),
  sensitivity: (changes: Change[], testData: boolean) =>
    request<SensitivityResponse>("/api/corridor/sensitivity", {
      method: "POST",
      body: JSON.stringify({ changes, testData }),
    }),
  calibration: () => request<CalibrationResponse>("/api/corridor/calibration"),
};

export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("ro-RO", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signed(n: number, digits = 1): string {
  if (Math.abs(n) < 0.5 * 10 ** -digits) return fmt(0, digits);
  return `${n > 0 ? "+" : "−"}${fmt(Math.abs(n), digits)}`;
}
