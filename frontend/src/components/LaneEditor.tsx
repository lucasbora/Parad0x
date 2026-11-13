import { Bike, Bus, Car, Loader2, TreeDeciduous, X } from "lucide-react";
import type { LaneUse } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  maxLanes: number;
  lanesAfter: number;
  use: LaneUse;
  running: boolean;
  disabled: boolean;
  onLanesAfter: (n: number) => void;
  onUse: (u: LaneUse) => void;
  onRun: () => void;
}

const USE_ICON = { bus: Bus, bike: Bike, sidewalk: TreeDeciduous, closed: X } as const;
const USE_COLOR: Record<LaneUse, string> = { bus: "#B91C1C", bike: "#059669", sidewalk: "#65A30D", closed: "#94a3b8" };

export default function LaneEditor({ maxLanes, lanesAfter, use, running, disabled, onLanesAfter, onUse, onRun }: Props) {
  const { t } = useI18n();
  const removed = maxLanes - lanesAfter;
  const closed = lanesAfter === 0;
  const lanes = Array.from({ length: maxLanes }, (_, i) => (i < lanesAfter ? "car" : closed ? "closed" : use));

  return (
    <section>
      <h2 className="text-[14px] font-semibold text-slate-900">{t.step2}</h2>

      <div className="mt-2 flex gap-1 rounded-lg bg-slate-200 p-1" aria-hidden>
        {lanes.map((l, i) => {
          const Icon = l === "car" ? Car : USE_ICON[l as LaneUse];
          const bg = l === "car" ? "#475569" : USE_COLOR[l as LaneUse];
          return (
            <div key={i} className="flex h-12 flex-1 items-center justify-center rounded-md text-white transition-colors" style={{ background: bg }}>
              <Icon size={18} />
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[12px] font-medium text-slate-700">{t.carLanesAfter}</p>
      <div className="mt-1 flex flex-wrap gap-1.5" role="radiogroup" aria-label={t.carLanesAfter}>
        {Array.from({ length: maxLanes + 1 }, (_, i) => maxLanes - i).map((n) => (
          <button
            key={n}
            role="radio"
            aria-checked={n === lanesAfter}
            onClick={() => onLanesAfter(n)}
            className={`min-w-[2.5rem] rounded-lg border px-3 py-1.5 font-mono text-[13px] font-semibold ${
              n === lanesAfter ? "border-[#005BBC] bg-[#005BBC] text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            {n}
          </button>
        ))}
      </div>

      {removed > 0 && !closed && (
        <>
          <p className="mt-3 text-[12px] font-medium text-slate-700">{t.removedBecomes}</p>
          <div className="mt-1 grid grid-cols-3 gap-1.5" role="radiogroup" aria-label={t.removedBecomes}>
            {(["bus", "bike", "sidewalk"] as LaneUse[]).map((u) => {
              const Icon = USE_ICON[u];
              return (
                <button
                  key={u}
                  role="radio"
                  aria-checked={u === use}
                  onClick={() => onUse(u)}
                  className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-2 text-[11.5px] font-medium ${
                    u === use ? "border-[#005BBC] bg-blue-50 text-[#005BBC]" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <Icon size={16} /> {t.uses[u]}
                </button>
              );
            })}
          </div>
        </>
      )}
      {closed && <p className="mt-2 text-[12px] font-medium text-red-700">{t.closedForCars}</p>}

      <button
        onClick={onRun}
        disabled={disabled || running || removed === 0}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-[#005BBC] px-4 py-2.5 text-[13.5px] font-semibold text-white hover:bg-[#004a99] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {running && <Loader2 size={15} className="animate-spin" />}
        {running ? t.running : t.run}
      </button>
      {removed === 0 && <p className="mt-1 text-[11px] text-slate-500">{t.noChange}</p>}
    </section>
  );
}
