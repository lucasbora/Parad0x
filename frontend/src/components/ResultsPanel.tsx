import { useEffect, useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import type { BusResult, CarRoute, Change, Highlight, Profile, SensitivityRow, SimulateResponse } from "../types/corridor";
import { api, fmt, signed } from "../api";
import { useI18n } from "../i18n/translations";
import SourceBadge from "./SourceBadge";

interface Props {
  result: SimulateResponse | null;
  changes: Change[];
  profile: Profile;
  onHoverBus: (b: BusResult | null) => void;
  onHighlight: (h: Highlight | null) => void;
  onFocus: (h: Highlight) => void;
}

function routeHighlight(c: CarRoute, minLabel: string): Highlight {
  return { coordinates: c.pathAfter, ghost: c.pathBefore, color: "#2563eb", label: `${c.from} → ${c.to}`,
    time: `${fmt(c.minutesAfter, 2)} ${minLabel}` };
}

function Delta({ before, after, unit, digits = 1, goodWhenLower = true }: {
  before: number; after: number; unit: string; digits?: number; goodWhenLower?: boolean;
}) {
  const d = after - before;
  const tone = Math.abs(d) < 0.5 * 10 ** -digits ? "text-slate-500" : (d < 0) === goodWhenLower ? "text-emerald-700" : "text-orange-700";
  return (
    <span className="whitespace-nowrap font-mono text-[12px]">
      <span className="text-slate-500">{fmt(before, digits)}</span>
      <ArrowRight size={11} className="mx-1 inline text-slate-400" />
      <b className="text-slate-900">{fmt(after, digits)}</b> {unit}{" "}
      <span className={tone}>({signed(d, digits)})</span>
    </span>
  );
}

export default function ResultsPanel({ result, changes, profile, onHoverBus, onHighlight, onFocus }: Props) {
  const { t } = useI18n();
  const [sens, setSens] = useState<SensitivityRow[] | null>(null);
  const [sensBusy, setSensBusy] = useState(false);
  useEffect(() => setSens(null), [result]);   // robustness table belongs to one scenario

  if (!result) return null;
  if (result.status === "needs_data") {
    return (
      <section>
        <h2 className="text-[14px] font-semibold text-slate-900">{t.step3}</h2>
        <p className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-[12.5px] text-amber-900">{t.needsDataResults}</p>
      </section>
    );
  }
  const r = result;
  const runSens = async () => {
    setSensBusy(true);
    try {
      const s = await api.sensitivity(changes, profile);
      if (s.status === "ok") setSens(s.rows);
    } finally {
      setSensBusy(false);
    }
  };
  const buses = r.buses.filter((b) => b.usesChangedStreet);

  return (
    <section className="space-y-4">
      <h2 className="text-[14px] font-semibold text-slate-900">{t.step3}</h2>
      {r.demandSource === "estimated" && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-[11.5px] font-semibold text-amber-800">{t.estimatedBanner}</p>
      )}

      <div className="rounded-lg bg-slate-50 p-3">
        <p className="text-[12px] text-slate-600">{t.totalTime}</p>
        <p className={`font-mono text-[22px] font-semibold ${r.totals.changePct <= 0 ? "text-emerald-700" : "text-orange-700"}`}>
          {signed(r.totals.changePct, 1)}%
        </p>
        <p className="font-mono text-[11px] text-slate-500">
          {fmt(r.totals.vehMinBefore / 60, 0)} → {fmt(r.totals.vehMinAfter / 60, 0)} veh·h · {fmt(r.totals.demandVehH, 0)} {t.vehH}
          {r.demandScale !== 1 && ` · ${t.demandMeter} ${Math.round(r.demandScale * 100)}%`}
        </p>
        <p className={`mt-1 text-[11.5px] ${r.braess.detected ? "font-semibold text-fuchsia-700" : "text-slate-500"}`}>
          {r.braess.detected ? `${t.braessTitle} ${t.braessBody} ${fmt(Math.abs(r.braess.totalChangePct), 2)}%.` : t.noBraess}
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 p-3">
        <h3 className="text-[12.5px] font-semibold text-slate-800">{t.peopleTitle}</h3>
        <div className="mt-1 space-y-1 text-[12px] text-slate-700">
          <div className="flex flex-wrap items-baseline justify-between gap-x-2">
            <span>{t.peopleInCars}</span>
            <Delta before={r.people.carPersonHoursBefore} after={r.people.carPersonHoursAfter} unit={t.personHours} digits={1} />
          </div>
          {r.people.busLinesCounted > 0 && (
            <div className="flex flex-wrap items-baseline justify-between gap-x-2">
              <span>{t.busTime} <span className="text-slate-400">· {r.people.busLinesCounted} {t.lines}</span></span>
              <Delta before={r.people.busHoursBefore} after={r.people.busHoursAfter} unit={t.busHours} digits={2} />
            </div>
          )}
        </div>
        <p className="mt-1 text-[10.5px] leading-snug text-slate-500">
          {t.peopleNote.replace("{occ}", fmt(r.people.carOccupancy, 1))}
        </p>
      </div>

      <div>
        <h3 className="text-[12.5px] font-semibold text-slate-800">{t.cars}</h3>
        <ul className="mt-1 divide-y divide-slate-100">
          {r.carRoutes.map((c) => (
            <li key={`${c.fromGate}-${c.toGate}`} className="-mx-1 cursor-pointer rounded-lg px-1 py-1.5 transition hover:bg-blue-50"
              onMouseEnter={() => onHighlight(routeHighlight(c, t.min))} onMouseLeave={() => onHighlight(null)}
              onClick={() => onFocus(routeHighlight(c, t.min))}>
              <div className="text-[12px] text-slate-700">{c.from} → {c.to} <span className="text-slate-400">· {fmt(c.vehH, 0)} {t.vehH}</span></div>
              <Delta before={c.minutesBefore} after={c.minutesAfter} unit={t.min} digits={2} />
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="text-[12.5px] font-semibold text-slate-800">{t.buses}</h3>
        {buses.length === 0 && <p className="text-[12px] text-slate-500">{t.noBuses}</p>}
        <ul className="mt-1 space-y-1.5">
          {buses.map((b) => (
            <li key={`${b.routeId}-${b.direction}`} onMouseEnter={() => onHoverBus(b)} onMouseLeave={() => onHoverBus(null)}
              className="rounded-lg border border-slate-200 p-2">
              <div className="flex items-center gap-2">
                <span className="rounded px-1.5 py-0.5 font-mono text-[12px] font-bold text-white" style={{ background: b.color }}>{b.shortName}</span>
                <span className="flex-1 truncate text-[11.5px] text-slate-600">{b.longName}</span>
              </div>
              <div className="mt-1"><Delta before={b.minutesBefore} after={b.minutesAfter} unit={t.min} digits={2} /></div>
              <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-slate-600">
                {b.busesPerHour !== null && <span className="font-mono">{b.busesPerHour} {t.busesPerHour}</span>}
                <SourceBadge label={b.busesPerHourSource} tone={b.busesPerHour !== null ? "live" : "seed"} />
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="text-[12.5px] font-semibold text-slate-800">{t.shifts}</h3>
        {r.trafficShifts.length === 0 && <p className="text-[12px] text-slate-500">{t.noShifts}</p>}
        <ul className="mt-1 divide-y divide-slate-100">
          {r.trafficShifts.map((s) => (
            <li key={`${s.street}-${s.heading}`} className="flex items-center justify-between gap-2 py-1 text-[12px]">
              <span className="truncate text-slate-700">{s.street} <span className="text-slate-400">· {t.heading[s.heading] ?? s.heading}</span></span>
              <span className={`font-mono ${s.deltaFlow < 0 ? "text-blue-700" : "text-orange-700"}`}>{signed(s.deltaFlow, 0)} {t.vehH}</span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="text-[12.5px] font-semibold text-slate-800">{t.intersections}</h3>
        <ul className="mt-1 divide-y divide-slate-100">
          {r.intersections.slice(0, 4).map((i) => (
            <li key={i.nodeId} className="py-1">
              <div className="truncate text-[12px] text-slate-700">{i.name}</div>
              <Delta before={i.delayBeforeSec} after={i.delayAfterSec} unit={t.s} digits={0} />
            </li>
          ))}
        </ul>
      </div>

      <div>
        <button onClick={runSens} disabled={sensBusy}
          className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-800 hover:bg-slate-50">
          {sensBusy && <Loader2 size={13} className="animate-spin" />} {t.sensitivity}
        </button>
        {sens && (
          <div className="mt-2">
            <p className="text-[11.5px] text-slate-600">{t.sensitivityTitle}</p>
            <table className="mt-1 w-full text-left font-mono text-[11px]">
              <thead className="text-slate-500">
                <tr><th className="font-normal">{t.demand}</th><th className="font-normal">{t.total}</th><th className="font-normal">{t.mainRoute}</th><th className="font-normal">{t.bus}</th></tr>
              </thead>
              <tbody>
                {sens.map((row) => (
                  <tr key={row.demandScale} className="border-t border-slate-100">
                    <td>{Math.round(row.demandScale * 100)}%</td>
                    <td className={row.braess ? "font-semibold text-fuchsia-700" : ""}>{signed(row.totalChangePct, 2)}%</td>
                    <td>{row.mainRoute ? `${signed(row.mainRoute.minutesAfter - row.mainRoute.minutesBefore, 2)} ${t.min}` : "—"}</td>
                    <td>{row.bus ? `${row.bus.shortName}: ${signed(row.bus.minutesAfter - row.bus.minutesBefore, 2)}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {r.warnings.map((w) => <p key={w} className="rounded bg-amber-50 px-2 py-1 text-[11px] text-amber-800">{w}</p>)}
      <p className="font-mono text-[10.5px] text-slate-400">
        Wardrop UE · CFW gap {r.solver.gapAfter.toExponential(0)} · {r.solver.iterationsAfter} it · {fmt(r.solver.msAfter, 0)} ms
      </p>
    </section>
  );
}
