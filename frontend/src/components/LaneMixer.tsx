import { Bike, Bus, Car, Loader2, RotateCcw, TreeDeciduous } from "lucide-react";
import type { LaneKind } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  lanes: LaneKind[];          // editable lanes (car lanes from OSM / field check)
  original: LaneKind[];
  existingBusLane: boolean;   // OSM says there is already a bus lane (not editable)
  segments: number;
  lanesSource: string;
  busy: boolean;
  onChange: (lanes: LaneKind[]) => void;
}

const KINDS: LaneKind[] = ["car", "bus", "bike", "sidewalk"];
const ICON = { car: Car, bus: Bus, bike: Bike, sidewalk: TreeDeciduous } as const;
const COLOR: Record<LaneKind, string> = { car: "#475569", bus: "#B91C1C", bike: "#059669", sidewalk: "#65A30D" };

export default function LaneMixer({ lanes, original, existingBusLane, segments, lanesSource, busy, onChange }: Props) {
  const { t } = useI18n();
  const changed = lanes.some((l, i) => l !== original[i]);

  return (
    <section>
      <div className="flex items-baseline justify-between">
        <h2 className="text-[14px] font-semibold text-slate-900">{t.step2}</h2>
        {busy && (
          <span className="flex items-center gap-1 text-[11px] text-slate-500">
            <Loader2 size={12} className="animate-spin" /> {t.recalculating}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-[11px] text-slate-500">
        {segments} {t.segments} · {lanesSource === "field check" ? t.fieldCheck : t.fromOsm} · {t.liveHint}
      </p>

      {/* lane strip */}
      <div className="mt-2 flex gap-1 rounded-lg bg-slate-200 p-1">
        <div className="w-3 shrink-0 rounded bg-slate-300" title="trotuar" />
        {lanes.map((l, i) => {
          const Icon = ICON[l];
          return (
            <div key={i} className="flex h-14 flex-1 items-center justify-center rounded-md text-white transition-colors duration-300"
              style={{ background: COLOR[l], backgroundImage: "repeating-linear-gradient(to bottom, rgba(255,255,255,.35) 0 8px, transparent 8px 16px)", backgroundSize: "2px 100%", backgroundRepeat: "no-repeat", backgroundPosition: "right" }}>
              <Icon size={20} />
            </div>
          );
        })}
        {existingBusLane && (
          <div className="flex h-14 flex-1 flex-col items-center justify-center rounded-md bg-[#7f1d1d] text-white opacity-80" title={t.existingBus}>
            <Bus size={18} />
            <span className="text-[8.5px] uppercase tracking-wide">{t.existingBus}</span>
          </div>
        )}
        <div className="w-3 shrink-0 rounded bg-slate-300" title="trotuar" />
      </div>

      {/* one dropdown per lane */}
      <div className="mt-2 grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.max(lanes.length, 1)}, minmax(0, 1fr))` }}>
        {lanes.map((l, i) => (
          <label key={i} className="block">
            <span className="block text-[10.5px] font-medium text-slate-500">{t.laneN} {i + 1}</span>
            <select
              value={l}
              onChange={(e) => {
                const next = [...lanes];
                next[i] = e.target.value as LaneKind;
                onChange(next);
              }}
              className={`mt-0.5 w-full rounded-md border px-1.5 py-1.5 text-[12px] focus:outline-none focus:ring-2 focus:ring-[#005BBC]/30 ${
                l !== original[i] ? "border-[#005BBC] bg-blue-50 font-semibold" : "border-slate-300 bg-white"
              }`}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>{t.laneKinds[k]}</option>
              ))}
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
