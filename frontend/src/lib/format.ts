import type { LaneType } from "../types/simulator";

export const PMT = {
  blue: "#005BBC",
  slate: "#0F172A",
  bg: "#F8FAFC",
  emerald: "#059669",
  amber: "#D97706",
  red: "#DC2626",
};

export const LANE_COLORS: Record<LaneType, string> = {
  car: "#475569",
  bus: "#B91C1C",
  bike: "#059669",
  pedestrian_trees: "#65A30D",
  parking_green: "#16A34A",
  parking_red: "#DC2626",
  parking_yellow: "#CA8A04",
  parking_blue: "#2563EB",
};

export const TIMPARK_COLORS: Record<string, string> = {
  green: "#16A34A",
  red: "#DC2626",
  yellow: "#EAB308",
  blue: "#2563EB",
};

export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("ro-RO", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signed(n: number, digits = 1): string {
  const s = fmt(Math.abs(n), digits);
  if (Math.abs(n) < 0.5 * 10 ** -digits) return fmt(0, digits);
  return `${n > 0 ? "+" : "−"}${s}`;
}

export function isParking(l: LaneType): boolean {
  return l.startsWith("parking_");
}

export function carLanes(lanes: LaneType[]): number {
  return lanes.filter((l) => l === "car").length;
}

export function sameLanes(a: LaneType[], b: LaneType[]): boolean {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

/** Replace the inner-most car lane (mirrors BraessEngine.one_lane_less). */
export function minusOneCar(lanes: LaneType[], replacement: LaneType): LaneType[] {
  const out = [...lanes];
  for (let i = out.length - 1; i >= 0; i--) {
    if (out[i] === "car") {
      out[i] = replacement;
      return out;
    }
  }
  return out;
}

export function fullClosure(lanes: LaneType[]): LaneType[] {
  const repl: LaneType[] = ["bus", "bike", "pedestrian_trees"];
  let k = 0;
  return lanes.map((l) => (l === "car" ? repl[k++ % repl.length] : l));
}
