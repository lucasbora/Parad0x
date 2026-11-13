import { ArrowUp, Bike, Bus, Car, Loader2, RotateCcw, TreeDeciduous } from "lucide-react";
import type { LaneKind } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  lanes: LaneKind[];
  original: LaneKind[];
  existingBusLane: boolean;
  segments: number;
  lanesSource: string;
  slowness: number;           // car travel time / free-flow time on this street (animates the cars)
  busy: boolean;
  onChange: (lanes: LaneKind[]) => void;
}

const KINDS: LaneKind[] = ["car", "bus", "bike", "sidewalk"];
const ICON = { car: Car, bus: Bus, bike: Bike, sidewalk: TreeDeciduous } as const;
const SURFACE: Record<LaneKind, string> = { car: "#334155", bus: "#991b1b", bike: "#047857", sidewalk: "#d6d3d1" };

/** Animated top-down lane: vehicles drive "up"; cars slow down when the street is congested. */
function LaneStrip({ kind, index, slowness, label }: { kind: LaneKind | "busExisting"; index: number; slowness: number; label?: string }) {
  const k: LaneKind = kind === "busExisting" ? "bus" : kind;
  const Icon = ICON[k];
  const moving = k !== "sidewalk";
  const base = k === "bike" ? 3.4 : k === "bus" ? 2.6 : 2.0;
  const dur = k === "car" ? base * Math.min(Math.max(slowness, 1), 3.5) : base;
  return (
    <div className="relative h-36 flex-1 overflow-hidden rounded-md transition-[background-color] duration-500"
      style={{ background: SURFACE[k], opacity: kind === "busExisting" ? 0.85 : 1 }}>
      {k !== "sidewalk" && (
        <div className="absolute inset-y-0 right-0 w-[2px]" style={{ backgroundImage: "repeating-linear-gradient(to bottom, rgba(255,255,255,0.75) 0 10px, transparent 10px 20px)" }} />
      )}
      {k === "bus" && <span className="absolute left-1/2 top-2 -translate-x-1/2 font-mono text-[10px] font-bold tracking-widest text-white/90">BUS</span>}
      {k === "bike" && <div className="absolute inset-x-1 inset-y-0 border-x-[3px] border-white/80" />}
      {moving && <ArrowUp size={14} className="absolute bottom-2 left-1/2 -translate-x-1/2 text-white/70" />}
      {moving && [0, 1].map((n) => (
        <span key={n} className="lane-vehicle absolute left-1/2 top-0 h-full"
          style={{ animationDuration: `${dur}s`, animationDelay: `${(-dur * n) / 2 - index * 0.37}s` }}>
          <Icon size={k === "bus" ? 22 : 18} className="text-white drop-shadow" strokeWidth={2.2} />
        </span>
      ))}
      {k === "sidewalk" && (
        <div className="absolute inset-0 flex flex-col items-center justify-around py-2">
          <TreeDeciduous size={22} className="text-emerald-700" />
          <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
          <TreeDeciduous size={22} className="text-emerald-700" />
        </div>
      )}
      {label && <span className="absolute inset-x-0 bottom-0 bg-black/35 py-0.5 text-center text-[8.5px] font-semibold uppercase tracking-wide text-white">{label}</span>}
    </div>
  );
}

/** Side view of the street under the animated strip. */
function CrossSection({ lanes }: { lanes: LaneKind[] }) {
  const w = 360, sw = 30, laneW = (w - 2 * sw) / Math.max(lanes.length, 1);
  return (
    <svg viewBox={`0 0 ${w} 64`} className="mt-2 h-14 w-full" aria-hidden>
      <rect x="0" y="46" width={sw} height="18" fill="#cbd5e1" />
      <rect x={w - sw} y="46" width={sw} height="18" fill="#cbd5e1" />
      {lanes.map((l, i) => {
        const x = sw + i * laneW;
        const raised = l === "sidewalk";
        return (
          <g key={i}>
            <rect x={x} y={raised ? 46 : 50} width={laneW - 1} height={raised ? 18 : 14} fill={raised ? "#cbd5e1" : SURFACE[l]} style={{ transition: "fill .4s" }} />
            {l === "sidewalk" && (
              <g transform={`translate(${x + laneW / 2},46)`}>
                <rect x="-1.5" y="-14" width="3" height="14" fill="#78350f" />
                <circle cx="0" cy="-22" r="11" fill="#16a34a" />
              </g>
            )}
            {l === "car" && <rect x={x + laneW / 2 - 9} y={38} width={18} height={11} rx={3} fill="#64748b" />}
            {l === "bus" && <rect x={x + laneW / 2 - 12} y={26} width={24} height={23} rx={3} fill="#b91c1c" />}
            {l === "bike" && (
              <g transform={`translate(${x + laneW / 2},44)`} stroke="#047857" strokeWidth="1.8" fill="none">
                <circle cx="-5" cy="0" r="4" />
                <circle cx="5" cy="0" r="4" />
                <path d="M-5 0 L0 -7 L5 0 M0 -7 L-2 -10" />
              </g>
            )}
          </g>
        );
      })}
      <g transform={`translate(${sw / 2},44)`} fill="#475569">
        <circle cx="0" cy="-16" r="3" />
        <rect x="-2.5" y="-12" width="5" height="11" rx="2" />
      </g>
    </svg>
  );
}

export default function LaneMixer({ lanes, original, existingBusLane, segments, lanesSource, slowness, busy, onChange }: Props) {
  const { t } = useI18n();
  const changed = lanes.some((l, i) => l !== original[i]);

  return (
    <section>
      <div className="flex items-baseline justify-between">
        <h2 className="text-[14px] font-semibold text-slate-900">{t.step2}</h2>
        {busy && <span className="flex items-center gap-1 text-[11px] text-slate-500"><Loader2 size={12} className="animate-spin" /> {t.recalculating}</span>}
      </div>
      <p className="mt-0.5 text-[11px] text-slate-500">
        {segments} {t.segments} · {lanesSource === "field check" ? t.fieldCheck : t.fromOsm} · {t.liveHint}
      </p>

      <div className="mt-2 rounded-xl bg-slate-100 p-2">
        <div className="flex items-stretch gap-1">
          <div className="flex w-6 shrink-0 flex-col items-center justify-around rounded-md bg-slate-300"><span className="h-1.5 w-1.5 rounded-full bg-slate-500" /></div>
          {lanes.map((l, i) => <LaneStrip key={i} kind={l} index={i} slowness={slowness} />)}
          {existingBusLane && <LaneStrip kind="busExisting" index={lanes.length} slowness={1} label={t.existingBus} />}
          <div className="flex w-6 shrink-0 flex-col items-center justify-around rounded-md bg-slate-300"><TreeDeciduous size={13} className="text-emerald-700/70" /></div>
        </div>
        <CrossSection lanes={existingBusLane ? [...lanes, "bus"] : lanes} />
      </div>

      <div className="mt-2 grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.max(lanes.length, 1)}, minmax(0, 1fr))` }}>
        {lanes.map((l, i) => (
          <label key={i} className="block">
            <span className="block text-[10.5px] font-medium text-slate-500">{t.laneN} {i + 1}</span>
            <select value={l}
              onChange={(e) => {
                const next = [...lanes];
                next[i] = e.target.value as LaneKind;
                onChange(next);
              }}
              className={`mt-0.5 w-full rounded-md border px-1.5 py-1.5 text-[12px] focus:outline-none focus:ring-2 focus:ring-[#005BBC]/30 ${
                l !== original[i] ? "border-[#005BBC] bg-blue-50 font-semibold" : "border-slate-300 bg-white"}`}>
              {KINDS.map((k) => <option key={k} value={k}>{t.laneKinds[k]}</option>)}
            </select>
          </label>
        ))}
      </div>
      {changed && (
        <button onClick={() => onChange(original)} className="mt-1.5 flex items-center gap-1 text-[11.5px] font-medium text-slate-500 hover:text-slate-900">
          <RotateCcw size={11} /> {t.resetLanes}
        </button>
      )}
    </section>
  );
}
