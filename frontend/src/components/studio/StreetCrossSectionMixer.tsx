import { useEffect, useRef, useState } from "react";
import { ArrowLeftRight, ArrowUp, Bike, Bus, Car, CircleParking, Loader2, RotateCcw, TreeDeciduous, X , type LucideIcon } from "lucide-react";
import { useI18n } from "../../i18n/translations";
import type { LaneType, RoadProps, UpdatedLink } from "../../types/simulator";
import { carLanes, fmt, fullClosure, isParking, LANE_COLORS, minusOneCar, sameLanes, signed } from "../../lib/format";
import DataProvenanceBadge from "./DataProvenanceBadge";

interface Props {
  link: RoadProps;
  lanes: LaneType[];
  filterCutThrough: boolean;
  update: UpdatedLink | null;
  simulating: boolean;
  onLanes: (lanes: LaneType[]) => void;
  onFilter: (v: boolean) => void;
  onSwitchDirection: (() => void) | null;
  onClose: () => void;
}

const ICONS: Record<LaneType, LucideIcon> = {
  car: Car,
  bus: Bus,
  bike: Bike,
  pedestrian_trees: TreeDeciduous,
  parking_green: CircleParking,
  parking_red: CircleParking,
  parking_yellow: CircleParking,
  parking_blue: CircleParking,
};

const SURFACE: Record<LaneType, string> = {
  car: "#334155",
  bus: "#991b1b",
  bike: "#047857",
  pedestrian_trees: "#d6d3d1",
  parking_green: "#3f6212",
  parking_red: "#7f1d1d",
  parking_yellow: "#854d0e",
  parking_blue: "#1e3a8a",
};

function laneOptions(original: LaneType): LaneType[] {
  const base: LaneType[] = ["car", "bus", "bike", "pedestrian_trees"];
  return isParking(original) ? [...base, original] : base;
}

/** Animated top-down lane strip: vehicles drive "up" at a speed tied to congestion. */
function LaneStrip({ type, index, onClick, open, slowness, label }: {
  type: LaneType;
  index: number;
  onClick: () => void;
  open: boolean;
  slowness: number;
  label: string;
}) {
  const Icon = ICONS[type];
  const moving = type === "car" || type === "bus" || type === "bike";
  const pedestrian = type === "pedestrian_trees";
  const parked = isParking(type);
  const base = type === "bike" ? 3.4 : type === "bus" ? 2.4 : 2.0;
  const dur = type === "car" ? base * Math.min(Math.max(slowness, 1), 3.5) : base;
  return (
    <button
      onClick={onClick}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-label={`${label} ${index + 1}`}
      className={`relative h-36 flex-1 overflow-hidden rounded-md transition-[background-color,box-shadow] duration-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#005BBC] ${
        open ? "ring-2 ring-[#005BBC] ring-offset-1" : "hover:ring-2 hover:ring-slate-300"
      }`}
      style={{ background: SURFACE[type] }}
    >
      {/* lane markings */}
      {!pedestrian && (
        <div className="absolute inset-y-0 right-0 w-[2px]" style={{ backgroundImage: "repeating-linear-gradient(to bottom, rgba(255,255,255,0.75) 0 10px, transparent 10px 20px)" }} />
      )}
      {type === "bus" && (
        <span className="absolute left-1/2 top-2 -translate-x-1/2 font-mono text-[10px] font-bold tracking-widest text-white/90">BUS</span>
      )}
      {type === "bike" && (
        <div className="absolute inset-x-1 inset-y-0 border-x-[3px] border-white/80" aria-hidden />
      )}
      {parked && (
        <div className="absolute inset-0" style={{ backgroundImage: "repeating-linear-gradient(to bottom, transparent 0 26px, rgba(255,255,255,0.6) 26px 28px)" }} />
      )}
      {(type === "car" || type === "bus" || type === "bike") && (
        <ArrowUp size={14} className="absolute bottom-2 left-1/2 -translate-x-1/2 text-white/70" aria-hidden />
      )}
      {moving &&
        [0, 1].map((k) => (
          <span
            key={k}
            className="absolute left-1/2 top-0 h-full -translate-x-1/2"
            style={{ animationName: "drive", animationDuration: `${dur}s`, animationTimingFunction: "linear", animationIterationCount: "infinite", animationDelay: `${(-dur * k) / 2 - index * 0.37}s` }}
            aria-hidden
          >
            <Icon size={type === "bus" ? 22 : 18} className="text-white drop-shadow" strokeWidth={2.2} />
          </span>
        ))}
      {pedestrian && (
        <div className="absolute inset-0 flex flex-col items-center justify-around py-2" aria-hidden>
          <TreeDeciduous size={22} className="text-emerald-700" />
          <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
          <TreeDeciduous size={22} className="text-emerald-700" />
        </div>
      )}
      {parked && (
        <div className="absolute inset-0 flex flex-col items-center justify-around" aria-hidden>
          <Car size={16} className="text-white/80" />
          <CircleParking size={14} className="text-white" />
          <Car size={16} className="text-white/80" />
        </div>
      )}
    </button>
  );
}

/** Small cross-section (side) profile under the top-down strip. */
function CrossSection({ lanes }: { lanes: LaneType[] }) {
  const w = 360;
  const sw = 34;
  const laneW = (w - 2 * sw) / lanes.length;
  return (
    <svg viewBox={`0 0 ${w} 64`} className="mt-2 h-14 w-full" role="img" aria-label="cross-section">
      <rect x="0" y="46" width={sw} height="18" fill="#cbd5e1" />
      <rect x={w - sw} y="46" width={sw} height="18" fill="#cbd5e1" />
      {lanes.map((l, i) => {
        const x = sw + i * laneW;
        const raised = l === "pedestrian_trees";
        return (
          <g key={i}>
            <rect x={x} y={raised ? 46 : 50} width={laneW - 1} height={raised ? 18 : 14} fill={raised ? "#cbd5e1" : SURFACE[l]} style={{ transition: "fill 0.4s" }} />
            {l === "pedestrian_trees" && (
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
            {isParking(l) && <rect x={x + laneW / 2 - 9} y={38} width={18} height={11} rx={3} fill="#94a3b8" />}
            {l === "bike" && <rect x={x} y={46} width={3} height={4} fill="#e2e8f0" />}
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

export default function StreetCrossSectionMixer(props: Props) {
  const { link, lanes, filterCutThrough, update, simulating, onLanes, onFilter, onSwitchDirection, onClose } = props;
  const { t } = useI18n();
  const [menuFor, setMenuFor] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const original = link.lanes;
  const changed = !sameLanes(lanes, original);
  const ff = (link.lengthM / 1000 / link.freeFlowSpeedKmh) * 3600;
  const slowness = (update ? update.travelTimeSec : link.travelTimeSec) / Math.max(ff, 1);

  useEffect(() => {
    if (menuFor === null) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuFor(null);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuFor(null);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  const setLane = (i: number, l: LaneType) => {
    const next = [...lanes];
    next[i] = l;
    onLanes(next);
    setMenuFor(null);
  };

  const quick: { label: string; lanes: LaneType[]; disabled: boolean }[] = [
    { label: t.modeClosure, lanes: fullClosure(original), disabled: carLanes(original) === 0 },
    { label: t.modeBus, lanes: minusOneCar(original, "bus"), disabled: carLanes(original) === 0 },
    { label: t.modeBike, lanes: minusOneCar(original, "bike"), disabled: carLanes(original) === 0 },
    { label: t.modeTrees, lanes: minusOneCar(original, "pedestrian_trees"), disabled: carLanes(original) === 0 },
  ];

  const scores = link.greenSuitabilityScores;

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white p-3.5" aria-label={t.streetCard}>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-[10.5px] font-semibold uppercase tracking-wider text-[#005BBC]">{t.streetCard}</p>
          <h2 className="truncate text-[16px] font-bold leading-tight text-slate-900" title={link.officialName ?? link.streetName}>
            {link.streetName}
          </h2>
          <p className="truncate text-[11.5px] text-slate-500">
            {t.direction}: {link.fromName} → {link.toName}
          </p>
        </div>
        {onSwitchDirection && (
          <button
            onClick={onSwitchDirection}
            title={t.switchDirection}
            aria-label={t.switchDirection}
            className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          >
            <ArrowLeftRight size={16} />
          </button>
        )}
        <button onClick={onClose} aria-label={t.close} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900">
          <X size={16} />
        </button>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        <DataProvenanceBadge
          label={`PMT Nomenclator Străzi · codGis #${link.codGis}`}
          tone={link.codGisSource === "seed" ? "seed" : "live"}
          title={link.codGisSource === "seed" ? undefined : `seed #${link.seedCodGis} · ${link.officialName ?? ""}`}
        />
        <DataProvenanceBadge label={link.cartier} />
        {link.hotspotId === "HOTSPOT_CLUJ_EROILOR" && <DataProvenanceBadge label="FIWARE Traffic Sensor · Cluj/Eroilor · Jul 2026" tone="live" />}
        {link.timparkZone && <DataProvenanceBadge label={`Timpark · ${link.timparkZone}`} />}
      </div>

      {/* top-down street */}
      <div className="relative mt-3 rounded-xl bg-slate-100 p-2">
        <div className="flex items-stretch gap-1">
          <div className="flex w-7 shrink-0 flex-col items-center justify-around rounded-md bg-slate-300" title={t.sidewalk}>
            {lanes[0] === "pedestrian_trees" ? <TreeDeciduous size={14} className="text-emerald-700" /> : <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />}
          </div>
          {lanes.map((l, i) => (
            <div key={i} className="relative flex flex-1">
              <LaneStrip
                type={l}
                index={i}
                open={menuFor === i}
                slowness={slowness}
                label={t.lane}
                onClick={() => setMenuFor(menuFor === i ? null : i)}
              />
              {menuFor === i && (
                <div
                  ref={menuRef}
                  role="menu"
                  className="absolute left-1/2 top-10 z-20 w-56 -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-1 shadow-island animate-slideIn"
                >
                  {laneOptions(original[i]).map((opt) => (
                    <button
                      key={opt}
                      role="menuitemradio"
                      aria-checked={l === opt}
                      onClick={() => setLane(i, opt)}
                      className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[12.5px] ${
                        l === opt ? "bg-blue-50 font-semibold text-[#005BBC]" : "text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <span className="h-3 w-3 rounded-sm" style={{ background: LANE_COLORS[opt] }} />
                      {t.laneLabels[opt]}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div className="flex w-7 shrink-0 flex-col items-center justify-around rounded-md bg-slate-300" title={t.sidewalk}>
            <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
            <TreeDeciduous size={14} className="text-emerald-700/70" />
          </div>
        </div>
        <CrossSection lanes={lanes} />
        <div className="mt-1 flex flex-wrap gap-1">
          {lanes.map((l, i) => (
            <span key={i} className={`rounded-md px-1.5 py-0.5 text-[10.5px] font-medium ${
              l !== original[i] ? "bg-emerald-100 text-emerald-800" : "bg-white text-slate-600"}`}>
              {i + 1}. {t.laneLabels[l]}
            </span>
          ))}
        </div>
        {simulating && (
          <div className="absolute right-3 top-3 flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[10.5px] text-slate-600 shadow">
            <Loader2 size={11} className="animate-spin" /> {t.simulating}
          </div>
        )}
      </div>
      <p className="mt-1 text-[10.5px] text-slate-400">{t.clickLaneHint}</p>

      {/* quick modes */}
      <div className="mt-2">
        <p className="text-[11px] font-semibold text-slate-700">{t.quickModes}</p>
        <div className="mt-1 grid grid-cols-2 gap-1">
          {quick.map((q) => {
            const on = sameLanes(q.lanes, lanes);
            return (
              <button
                key={q.label}
                disabled={q.disabled}
                onClick={() => onLanes(q.lanes)}
                className={`rounded-lg border px-2 py-1.5 text-[11.5px] font-medium transition disabled:opacity-40 ${
                  on ? "border-[#059669] bg-emerald-50 text-emerald-800" : "border-slate-200 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {q.label}
              </button>
            );
          })}
        </div>
        {changed && (
          <button onClick={() => onLanes(original)} className="mt-1 flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-900">
            <RotateCcw size={11} /> {t.modeReset}
          </button>
        )}
      </div>

      {/* filter toggle */}
      <label className="mt-3 flex cursor-pointer items-start gap-2.5 rounded-xl border border-slate-200 p-2.5 hover:bg-slate-50">
        <span className="relative mt-0.5 inline-flex h-5 w-9 shrink-0">
          <input type="checkbox" className="peer sr-only" checked={filterCutThrough} onChange={(e) => onFilter(e.target.checked)} />
          <span className="absolute inset-0 rounded-full bg-slate-300 transition peer-checked:bg-[#059669] peer-focus-visible:ring-2 peer-focus-visible:ring-[#005BBC]" />
          <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition peer-checked:translate-x-4" />
        </span>
        <span>
          <span className="block text-[12px] font-medium leading-snug text-slate-800">{t.filterCutThrough}</span>
          <span className="block text-[10.5px] text-slate-500">{t.filterCutThroughHint}</span>
        </span>
      </label>

      {/* link stats + suitability */}
      <div className="mt-3 grid grid-cols-3 gap-1.5 font-mono text-[11px]">
        <div className="rounded-lg bg-slate-50 p-1.5">
          <div className="font-sans text-[10px] text-slate-500">{t.flow}</div>
          <div className="text-slate-900">{fmt(update?.flow ?? link.baselineFlow, 0)}</div>
          {update && Math.abs(update.deltaFlow) > 0.5 && (
            <div className={update.deltaFlow < 0 ? "text-emerald-700" : "text-amber-700"}>{signed(update.deltaFlow, 0)}</div>
          )}
        </div>
        <div className="rounded-lg bg-slate-50 p-1.5">
          <div className="font-sans text-[10px] text-slate-500">{t.capacity}</div>
          <div className="text-slate-900">{fmt(update?.capacity ?? link.capacity, 0)}</div>
          <div className="text-slate-500">v/c {fmt(update?.vOverC ?? link.vOverC, 2)}</div>
        </div>
        <div className="rounded-lg bg-slate-50 p-1.5">
          <div className="font-sans text-[10px] text-slate-500">{t.prescanV}</div>
          <div className={link.braessValueV !== null && link.braessValueV < 0 ? "text-emerald-700" : "text-slate-900"}>
            {link.braessValueV === null ? "—" : signed(link.braessValueV, 0)}
          </div>
          <div className="text-slate-500">{t.vehMin}</div>
        </div>
      </div>
      <div className="mt-2">
        <p className="text-[11px] font-semibold text-slate-700">{t.greenSuitability}</p>
        <div className="mt-1 space-y-1">
          {([["bus", t.bus, "#B91C1C"], ["bike", t.bike, "#059669"], ["trees", t.trees, "#65A30D"]] as const).map(([k, label, c]) => (
            <div key={k} className="flex items-center gap-2 text-[11px]">
              <span className="w-16 text-slate-600">{label}</span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                <span className="block h-full rounded-full" style={{ width: `${scores[k]}%`, background: c }} />
              </span>
              <span className="w-7 text-right font-mono text-slate-700">{scores[k]}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
