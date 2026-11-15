import { useEffect, useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import type { AllDay, BreakEvenOk, BusResult, CarRoute, Change, Highlight, Profile, ProfileMeta, SimulateResponse,
  TripChange, TripCosts } from "../types/corridor";
import { api, fmt, signed } from "../api";
import { useI18n } from "../i18n/translations";
import { useSlidingThumb, useTween } from "../motion";
import SourceBadge from "./SourceBadge";
import Collapse from "./Collapse";

interface Props {
  result: SimulateResponse | null;
  changes: Change[];
  profile: Profile;
  busy: boolean;
  onHoverBus: (b: BusResult | null) => void;
  onHighlight: (h: Highlight | null) => void;
  onFocus: (h: Highlight) => void;
  tripCosts?: TripCosts;
  profiles?: ProfileMeta[];
  evaporation?: number;
  onEvaporation?: (v: number) => void;
  evapOptions?: { literature_median: number; cautious: number; source: string };
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
    <span className="whitespace-nowrap font-secondary text-[12px]">
      <span className="text-slate-500">{fmt(before, digits)}</span>
      <ArrowRight size={11} className="mx-1 inline text-slate-400" />
      <b className="text-slate-900">{fmt(after, digits)}</b> {unit}{" "}
      <span className={tone}>({signed(d, digits)})</span>
    </span>
  );
}

export default function ResultsPanel({ result, changes, profile, busy, onHoverBus, onHighlight, onFocus, tripCosts, profiles,
  evaporation = 0, onEvaporation, evapOptions }: Props) {
  const { t, lang } = useI18n();
  // the headline number counts to its new value instead of jumping
  const totalPct = useTween(result && result.status === "ok" ? result.totals.changePct : 0);
  const evapThumb = useSlidingThumb(String(evaporation));

  // the same change in every time window
  const [allDay, setAllDay] = useState<AllDay | null>(null);
  useEffect(() => {
    setAllDay(null);
    if (!result || result.status !== "ok") return;
    const ctl = new AbortController();
    api.allday(changes, profile, ctl.signal, evaporation).then((a) => setAllDay(a.profiles)).catch(() => undefined);
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  // break-even only for lanes given to bus / bike / sidewalk (not for full closures)
  const laneTaken = changes.some((c) => c.use !== "closed" && c.carLanesAfter > 0);
  const [be, setBe] = useState<BreakEvenOk | null>(null);
  useEffect(() => {
    setBe(null);
    if (!result || result.status !== "ok" || !laneTaken) return;
    const ctl = new AbortController();
    api.breakeven(changes, profile, result.demandScale, ctl.signal).then(setBe).catch(() => undefined);
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  if (!result) return null;
  if (result.status === "needs_data") {
    return (
      <section className="m-rise-in">
        <h2 className="text-[14px] font-semibold text-slate-900">{t.step3}</h2>
        <p className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-[12.5px] text-amber-900">{t.needsDataResults}</p>
      </section>
    );
  }
  const r = result;
  const buses = r.buses.filter((b) => b.usesChangedStreet);

  return (
    <section className={`m-rise-in space-y-4 transition-opacity duration-300 ${busy ? "opacity-60" : "opacity-100"}`} aria-busy={busy}>
      <h2 className="text-[14px] font-semibold text-slate-900">{t.step3}</h2>

      {r.braess.carCapacityRemoved && onEvaporation && evapOptions && (
        <div className="rounded-lg border border-slate-200 p-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[12.5px] font-semibold text-slate-800">{t.evapTitle}</h3>
            <div ref={evapThumb.ref} className="relative flex rounded-full bg-slate-100 p-0.5 font-secondary text-[11.5px]" role="radiogroup" aria-label={t.evapTitle}>
              <span aria-hidden="true" style={evapThumb.style}
                className="absolute left-0 top-0 rounded-full bg-white shadow-sm transition-[transform,width,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]" />
              {[0, evapOptions.cautious, evapOptions.literature_median].map((v) => (
                <button key={v} type="button" role="radio" data-thumb-key={String(v)} aria-checked={evaporation === v} onClick={() => onEvaporation(v)}
                  title={v === evapOptions.cautious ? t.evapCautious : v === evapOptions.literature_median ? t.evapLiterature : undefined}
                  className={`relative rounded-full px-2.5 py-0.5 font-semibold transition-colors duration-300 ${evaporation === v ? "text-[#005BBC]" : "text-slate-500 hover:text-slate-800"}`}>
                  {Math.round(v * 100)}%
                </button>
              ))}
            </div>
          </div>
          <p className="mt-1 text-[11px] leading-snug text-slate-500">{t.evapHint}</p>
          <Collapse open={!!r.evaporation}>
            {r.evaporation && (
              <div className="mt-1.5 space-y-0.5 text-[12px] text-slate-700">
                <p><b className="font-secondary">{fmt(r.evaporation.carsLeftVehH, 0)}</b> {t.evapLeft}</p>
                {r.evaporation.stayingDriversChangePct !== null && (
                  <p>
                    {t.evapStaying}:{" "}
                    <b className={`font-secondary ${r.evaporation.stayingDriversChangePct <= 0 ? "text-emerald-700" : "text-orange-700"}`}>
                      {signed(r.evaporation.stayingDriversChangePct, 2)}%
                    </b>{" "}
                    <span className="text-slate-500">{r.evaporation.stayingDriversChangePct <= 0 ? t.evapStayFaster : t.evapStaySlower}</span>
                  </p>
                )}
                <p className="text-[10.5px] text-slate-400">{r.evaporation.source}</p>
              </div>
            )}
          </Collapse>
        </div>
      )}
      <div className="rounded-lg bg-slate-50 p-3">
        <p className="text-[12px] text-slate-600">{r.evaporation ? `${t.evapTotalLabel} ${Math.round(r.evaporation.share * 100)}%)` : t.totalTime}</p>
        <p className={`font-secondary text-[22px] font-semibold transition-colors duration-300 ${r.totals.changePct <= 0 ? "text-emerald-700" : "text-orange-700"}`}>
          {signed(totalPct, 2)}%
        </p>
        <p className="font-secondary text-[11px] text-slate-500">
          {fmt(r.totals.vehMinBefore / 60, 0)} → {fmt(r.totals.vehMinAfter / 60, 0)} veh·h · {fmt(r.totals.demandVehH, 0)} {t.vehH}
          {r.demandScale !== 1 && ` · ${t.demandMeter} ${Math.round(r.demandScale * 100)}%`}
        </p>
        <p className={`mt-1 text-[11.5px] ${r.braess.detected ? "font-semibold text-fuchsia-700"
          : r.evaporation && r.totals.changePct < 0 ? "font-semibold text-emerald-700" : "text-slate-500"}`}>
          {r.braess.detected ? `${t.braessBody} ${fmt(Math.abs(r.braess.totalChangePct), 2)}%.`
            : r.evaporation ? (r.totals.changePct < 0 ? t.evapImproves : t.evapWorse) : t.noBraess}
        </p>
      </div>

      <Collapse open={!!allDay && !!profiles}>
        {allDay && profiles && (
          <div>
            <h3 className="text-[12.5px] font-semibold text-slate-800">{t.allDayTitle}</h3>
            <div className="mt-1 grid grid-cols-4 gap-1">
              {profiles.map((p) => {
                const v = allDay[p.id];
                const tone = !v ? "border-slate-200 text-slate-400" : v.changePct < -0.005 ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : v.changePct > 0.005 ? "border-orange-200 bg-orange-50 text-orange-800" : "border-slate-200 text-slate-600";
                return (
                  <div key={p.id} className={`rounded-lg border px-1.5 py-1 text-center ${tone} ${p.id === profile ? "ring-1 ring-[#005BBC]" : ""}`}>
                    <div className="truncate text-[11px] font-medium">{lang === "ro" ? p.labelRo : p.labelEn}</div>
                    <div className="font-secondary text-[12px] font-semibold">{v ? `${signed(v.changePct, 2)}%` : "—"}</div>
                  </div>
                );
              })}
            </div>
            {Object.values(allDay).some((v) => v && v.changePct > 0.005) && Object.values(allDay).some((v) => v && v.changePct < -0.005) && (
              <p className="mt-1 text-[11px] text-slate-500">{t.allDayHint}</p>
            )}
          </div>
        )}
      </Collapse>

      {r.local && <LocalBlock local={r.local} />}

      {laneTaken && (
        <div className="rounded-lg border border-slate-200 p-3">
          <h3 className="text-[12.5px] font-semibold text-slate-800">{t.breakEvenTitle}</h3>
          {!be && <p className="mt-1 flex items-center gap-1.5 text-[11.5px] text-slate-500"><Loader2 size={12} className="animate-spin" /> {t.breakEvenBusy}</p>}
          {be && be.free && <p className="mt-1 text-[12px] font-medium text-emerald-700">{t.breakEvenFree}</p>}
          {be && !be.free && be.switchVehH !== null && (
            <p className="mt-1 text-[12px] leading-snug text-slate-700">
              {t.breakEvenIf} <b className="font-secondary">{fmt(be.switchVehH, 1)}</b> {t.breakEvenOf}{" "}
              <span className="font-secondary">{fmt(be.streetUsersVehH, 0)}</span> {t.breakEvenUsers}
              {be.switchVehH > 0 && <span className="font-secondary text-slate-500"> ({t.breakEvenOneIn} {fmt(Math.max(1, be.streetUsersVehH / be.switchVehH), 0)})</span>}.
            </p>
          )}
          {be && !be.free && be.switchVehH === null && <p className="mt-1 text-[12px] text-orange-700">{t.breakEvenAbove}</p>}
          {r.modeShift && buses.length > 0 && (
            <p className="mt-1.5 text-[11px] leading-snug text-slate-500">
              <span className="font-semibold">{t.surveyLabel}:</span>{" "}
              {r.modeShift.belowSmallestOption
                ? <>{fmt(r.modeShift.minutesFaster, 2)} {t.surveyBelow} ({r.modeShift.belowSmallestOption} min).</>
                : <><span className="font-secondary">{Math.round((r.modeShift.share ?? 0) * 100)}%</span> {t.surveyShare} {r.modeShift.option} min.</>}{" "}
              <span className="font-secondary">{r.modeShift.source}</span> · {t.statedPref}
            </p>
          )}
        </div>
      )}
      <div>
        <h3 className="text-[12.5px] font-semibold text-slate-800">{t.cars}</h3>
        {r.carRoutes.length === 0 && <p className="mt-1 text-[12px] text-slate-500">{t.noRouteChange}</p>}
        <ul className="mt-1 divide-y divide-slate-100">
          {r.carRoutes.map((c) => (
            <li key={`${c.fromGate}-${c.toGate}`} className="-mx-1 cursor-pointer rounded-lg px-1 py-1.5 transition hover:bg-blue-50"
              onMouseEnter={() => onHighlight(routeHighlight(c, t.min))} onMouseLeave={() => onHighlight(null)}
              onClick={() => onFocus(routeHighlight(c, t.min))}>
              <div className="text-[12px] text-slate-700">{c.from} → {c.to} <span className="text-slate-400">· {fmt(c.vehH, 0)} {t.vehH}</span></div>
              <span className="whitespace-nowrap font-secondary text-[12px]">
                <span className="text-slate-500">{fmt(c.minutesBefore, 2)}</span>
                <ArrowRight size={11} className="mx-1 inline text-slate-400" />
                <b className="text-slate-900">{fmt(c.minutesAfter, 2)}</b> {t.min}{" "}
                {c.secondsChange !== undefined && (
                  <span className={c.secondsChange < 0 ? "text-emerald-700" : "text-orange-700"}>({signed(c.secondsChange, 0)} {t.s})</span>
                )}
              </span>
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
                <span className="rounded px-1.5 py-0.5 font-secondary text-[12px] font-bold text-white" style={{ background: b.color }}>{b.shortName}</span>
                <span className="flex-1 truncate text-[11.5px] text-slate-600">{b.longName}</span>
              </div>
              <div className="mt-1"><Delta before={b.minutesBefore} after={b.minutesAfter} unit={t.min} digits={2} /></div>
              <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-slate-600">
                {b.busesPerHour !== null && <span className="font-secondary">{b.busesPerHour} {t.busesPerHour}</span>}
                <SourceBadge label={b.busesPerHourSource} tone={b.busesPerHour !== null ? "live" : "seed"} />
              </div>
            </li>
          ))}
        </ul>
      </div>

      {tripCosts && (tripCosts.ticket || tripCosts.parking) && <CostsLine c={tripCosts} />}

      <div>
        <h3 className="text-[12.5px] font-semibold text-slate-800">{t.shifts}</h3>
        {r.trafficShifts.length === 0 && <p className="text-[12px] text-slate-500">{t.noShifts}</p>}
        <ul className="mt-1 divide-y divide-slate-100">
          {r.trafficShifts.map((s) => (
            <li key={`${s.street}-${s.heading}`} className="flex items-center justify-between gap-2 py-1 text-[12px]">
              <span className="truncate text-slate-700">{s.street} <span className="text-slate-400">· {t.heading[s.heading] ?? s.heading}</span></span>
              <span className={`font-secondary ${s.deltaFlow < 0 ? "text-blue-700" : "text-orange-700"}`}>{signed(s.deltaFlow, 0)} {t.vehH}</span>
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

      {r.warnings.map((w) => <p key={w} className="rounded bg-amber-50 px-2 py-1 text-[11px] text-amber-800">{w}</p>)}
    </section>
  );
}

function TripLine({ label, trip, good }: { label: string; trip: TripChange; good: boolean }) {
  const { t } = useI18n();
  return (
    <li className="py-1">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="truncate text-[12px] text-slate-700" title={`${trip.from} → ${trip.to}`}>
        {trip.from} → {trip.to} <span className="text-slate-400">· {fmt(trip.vehH, 0)} {t.vehH}</span>
      </div>
      <span className="whitespace-nowrap font-secondary text-[12px]">
        <span className="text-slate-500">{fmt(trip.minutesBefore, 2)}</span>
        <ArrowRight size={11} className="mx-1 inline text-slate-400" />
        <b className="text-slate-900">{fmt(trip.minutesAfter, 2)}</b> {t.min}{" "}
        <span className={good ? "text-emerald-700" : "text-orange-700"}>({signed(trip.changePct, 1)}%)</span>
      </span>
    </li>
  );
}

function LocalBlock({ local }: { local: NonNullable<Extract<SimulateResponse, { status: "ok" }>["local"]> }) {
  const { t } = useI18n();
  const saved = local.vehHSavedPerHour;
  const side = [
    local.sideStreetRelieved && { label: t.sideRelieved, s: local.sideStreetRelieved, tone: "text-blue-700" },
    local.sideStreetLoaded && { label: t.sideLoaded, s: local.sideStreetLoaded, tone: "text-orange-700" },
  ].filter((x): x is { label: string; s: NonNullable<typeof local.sideStreetRelieved>; tone: string } => !!x);
  return (
    <div>
      <h3 className="text-[12.5px] font-semibold text-slate-800">{t.whereFelt}</h3>
      {Math.abs(saved) >= 0.05 && (
        <p className="mt-0.5 text-[12px] text-slate-700">
          <b className={`font-secondary ${saved > 0 ? "text-emerald-700" : "text-orange-700"}`}>{fmt(Math.abs(saved), 1)}</b>{" "}
          {saved > 0 ? t.savedPerPeak : t.costPerPeak}
          <span className="block font-secondary text-[11px] text-slate-500">≈ {fmt(Math.abs(saved) * 250, 0)} veh·h {t.perYear}</span>
        </p>
      )}
      <ul className="mt-1 divide-y divide-slate-100">
        {local.bestTrip && <TripLine label={t.bestTrip} trip={local.bestTrip} good />}
        {local.worstTrip && <TripLine label={t.worstTrip} trip={local.worstTrip} good={false} />}
        {side.map(({ label, s, tone }) => (
          <li key={label} className="flex items-center justify-between gap-2 py-1 text-[12px]">
            <span className="min-w-0">
              <span className="block text-[11px] text-slate-500">{label}</span>
              <span className="block truncate text-slate-700">{s.street} <span className="text-slate-400">· {t.heading[s.heading] ?? s.heading}</span></span>
            </span>
            <span className={`whitespace-nowrap font-secondary ${tone}`}>{signed(s.deltaFlow, 0)} {t.vehH}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CostsLine({ c }: { c: TripCosts }) {
  const { t } = useI18n();
  const seg = c.parking ? Object.entries(c.parking.streetSegmentsByTariff) : [];
  const total = seg.reduce((a, [, n]) => a + n, 0);
  const [top, topN] = seg[0] ?? [null, 0];
  const hours = c.parking?.schedule?.weekdays;
  return (
    <div>
      <h3 className="text-[12.5px] font-semibold text-slate-800">{t.costsTitle}</h3>
      <div className="mt-1 space-y-0.5 text-[12px] leading-snug text-slate-700">
        {c.ticket && (
          <p>
            {t.ticketLabel}: <b className="font-secondary">{c.ticket.lei} lei</b> / {c.ticket.minutes} min
            {c.ticket.dayPassLei ? <> · {t.dayPass} <span className="font-secondary">{c.ticket.dayPassLei} lei</span></> : null}
          </p>
        )}
        {c.parking && top && (
          <p>
            {t.parkingLabel}: {t.parkingMostly} {t.tariffNames[top] ?? top}{" "}
            <b className="font-secondary">€{fmt(c.parking.eurPerHour[top], 2)}/h</b>{" "}
            <span className="text-slate-500">({topN} {t.segmentsOf} {total}{hours ? `, ${t.weekdays} ${hours[0]}–${hours[1]}` : ""})</span>
          </p>
        )}
        <p className="flex flex-wrap gap-1 pt-0.5">
          {c.ticket && <SourceBadge label={c.ticket.source} tone="live" />}
          {c.parking && <SourceBadge label={c.parking.source} tone="live" />}
        </p>
      </div>
    </div>
  );
}
