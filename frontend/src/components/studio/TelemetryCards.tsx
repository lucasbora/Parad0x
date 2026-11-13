import type { ReactNode } from "react";
import { Bus, Gauge, Leaf, ParkingCircle, Timer, TrendingDown , type LucideIcon } from "lucide-react";
import { useI18n } from "../../i18n/translations";
import type { Metrics, NetworkResponse } from "../../types/simulator";
import { fmt, signed } from "../../lib/format";
import DataProvenanceBadge from "./DataProvenanceBadge";

interface Props {
  baseline: Metrics | null;
  simulated: Metrics | null;
  network: NetworkResponse | null;
}

function Card({ icon: Icon, title, value, unit, sub, good, badge }: {
  icon: LucideIcon;
  title: string;
  value: string;
  unit?: string;
  sub?: ReactNode;
  good?: boolean | null;
  badge: string;
}) {
  const tone = good === null || good === undefined ? "text-slate-900" : good ? "text-[#059669]" : "text-[#D97706]";
  return (
    <div className="flex min-w-0 flex-col rounded-xl border border-slate-200 bg-white p-2.5">
      <div className="flex items-center gap-1.5 text-[10.5px] font-medium text-slate-500">
        <Icon size={12} className="shrink-0" aria-hidden />
        <span className="truncate">{title}</span>
      </div>
      <div className={`mt-1 font-mono text-[17px] font-semibold leading-none ${tone}`}>
        {value}
        {unit && <span className="ml-1 text-[10px] font-normal text-slate-500">{unit}</span>}
      </div>
      {sub && <div className="mt-1 font-mono text-[10px] text-slate-500">{sub}</div>}
      <div className="mt-1.5">
        <DataProvenanceBadge label={badge} />
      </div>
    </div>
  );
}

/** Network-wide telemetry: V, I_th, queues, CO₂, STPT riders, Timpark. */
export default function TelemetryCards({ baseline, simulated, network }: Props) {
  const { t } = useI18n();
  const m = simulated ?? baseline;
  if (!m || !baseline) return null;
  const has = !!simulated;
  const model = `Wardrop · CFW gap ${m.solverRelativeGap.toExponential(0)}`;
  const parkingProv = network?.provenance.find((p) => p.dataset === "parking");
  return (
    <section aria-label={t.telemetry}>
      <div className="mb-1.5 flex items-center justify-between">
        <h3 className="text-[12px] font-semibold text-slate-800">{t.telemetry}</h3>
        <span className="font-mono text-[10px] text-slate-400">
          {t.solver}: {m.solverIterations} it · {fmt(m.solverMs, 1)} ms
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        <Card
          icon={TrendingDown}
          title={t.braessValue}
          value={has ? signed(m.braessValueV, 1) : "0,0"}
          unit={t.vehMin}
          good={has ? m.braessValueV < 0 : null}
          sub={`Y = ${fmt(m.totalSystemDelayVehMin, 0)}`}
          badge={model}
        />
        <Card
          icon={Gauge}
          title={t.delayReduction}
          value={`${has ? signed(m.delayReductionPct, 2) : "0,00"}%`}
          good={has ? m.delayReductionPct > 0 : null}
          sub={`I_th = (Y − Y′)/Y`}
          badge="Burov et al. · Beckmann"
        />
        <Card
          icon={Timer}
          title={t.avgQueue}
          value={fmt(m.avgIntersectionQueueSec, 1)}
          unit="s"
          good={has ? m.avgIntersectionQueueSec < baseline.avgIntersectionQueueSec - 0.05 : null}
          sub={has ? `${fmt(baseline.avgIntersectionQueueSec, 1)} → ${fmt(m.avgIntersectionQueueSec, 1)} s` : undefined}
          badge="Phantom queue links"
        />
        <Card
          icon={Leaf}
          title={t.co2Saved}
          value={has ? signed(m.co2SavedKgPerHour, 1) : "0,0"}
          unit="kg/h"
          good={has ? m.co2SavedKgPerHour > 0 : null}
          sub={`${fmt(m.co2KgPerHour, 0)} kg/h total`}
          badge="0,17 kg/veh·km · idle"
        />
        <Card
          icon={Bus}
          title={t.stptRiders}
          value={fmt(m.stptRidersBenefitingPerHour, 0)}
          unit={t.perHour}
          good={has ? m.stptRidersBenefitingPerHour > 0 : null}
          badge={`SMTT GTFS v${network?.feedVersion ?? "4.31-4"}`}
        />
        <Card
          icon={ParkingCircle}
          title={t.timparkSpaces}
          value={has ? signed(m.timparkSpacesDelta, 0) : "0"}
          sub={has ? `${signed(m.timparkHourlyRevenueDeltaEur, 2)} €/h` : undefined}
          good={null}
          badge={`Timpark · ${parkingProv?.source ?? "seed"} · SMS 7406`}
        />
      </div>
    </section>
  );
}
