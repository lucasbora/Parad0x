import { useState } from "react";
import { Bike, Car, Clock, FlaskConical, Leaf, MessageSquareWarning, Sigma } from "lucide-react";
import { useI18n } from "../../i18n/translations";
import type {
  BikeRoute,
  BprChart,
  CarRoute,
  HighlightedRoute,
  QueueChart,
  SimulateResponse,
  StptRoute,
} from "../../types/simulator";
import { fmt, signed } from "../../lib/format";
import DataProvenanceBadge from "./DataProvenanceBadge";

interface Props {
  sim: SimulateResponse;
  onHover: (r: HighlightedRoute | null) => void;
  onFocus: (r: HighlightedRoute) => void;
  onExplain: () => void;
}

type Tab = "green" | "car" | "math";

const TYPE_LABEL: Record<number, string> = { 0: "Tram", 3: "Bus", 11: "Troleibuz" };

function stptHighlight(r: StptRoute): HighlightedRoute {
  return {
    id: r.routeId,
    kind: "stpt",
    color: r.color,
    coordinates: r.coordinates,
    label: `${TYPE_LABEL[r.type] ?? "STPT"} ${r.shortName}`,
    timeLabel: `${fmt(r.newCorridorTimeMin, 1)} min`,
  };
}

function bikeHighlight(r: BikeRoute): HighlightedRoute {
  return { id: r.routeId, kind: "bike", color: "#059669", coordinates: r.coordinates, label: r.name, timeLabel: `${fmt(r.timeMin, 1)} min` };
}

function carHighlight(r: CarRoute): HighlightedRoute {
  const cut = r.role === "throttled_braess_cut_through";
  return {
    id: r.id,
    kind: cut ? "car_cut_through" : "car_arterial",
    color: cut ? "#dc2626" : "#2563eb",
    coordinates: r.coordinates,
    label: r.name,
    timeLabel: r.filteredFromNavigation ? "—" : `${fmt(r.newTimeMin, 1)} min`,
  };
}

/** Minimal dependency-free line chart for Φ curves. */
function CurveChart({ before, after, xBefore, xAfter, sBefore, sAfter, yLabel, xLabel }: {
  before: [number, number][];
  after: [number, number][];
  xBefore: number;
  xAfter: number;
  sBefore?: number;
  sAfter?: number;
  yLabel: string;
  xLabel: string;
}) {
  const { t } = useI18n();
  const W = 340, H = 150, L = 34, B = 22, T = 8, R = 8;
  const xs = [...before, ...after].map((p) => p[0]);
  const ys = [...before, ...after].map((p) => p[1]);
  const xmax = Math.max(...xs, xBefore, xAfter, 1);
  const ymax = Math.max(...ys, 1) * 1.05;
  const X = (x: number) => L + (x / xmax) * (W - L - R);
  const Y = (y: number) => H - B - (y / ymax) * (H - B - T);
  const path = (pts: [number, number][]) => pts.map((p, i) => `${i ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" ");
  const interp = (pts: [number, number][], x: number) => {
    for (let i = 1; i < pts.length; i++) {
      if (pts[i][0] >= x) {
        const [x0, y0] = pts[i - 1];
        const [x1, y1] = pts[i];
        return y0 + ((y1 - y0) * (x - x0)) / Math.max(x1 - x0, 1e-9);
      }
    }
    return pts[pts.length - 1][1];
  };
  const yB = interp(before, xBefore);
  const yA = interp(after, xAfter);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={yLabel}>
      <line x1={L} y1={H - B} x2={W - R} y2={H - B} stroke="#cbd5e1" />
      <line x1={L} y1={T} x2={L} y2={H - B} stroke="#cbd5e1" />
      {[0, 0.5, 1].map((f) => (
        <text key={f} x={L - 4} y={Y(ymax * f) + 3} textAnchor="end" className="fill-slate-400 font-mono" fontSize="9">
          {Math.round(ymax * f)}
        </text>
      ))}
      {[0, 0.5, 1].map((f) => (
        <text key={f} x={X(xmax * f)} y={H - 8} textAnchor="middle" className="fill-slate-400 font-mono" fontSize="9">
          {Math.round(xmax * f)}
        </text>
      ))}
      <text x={W - R} y={H - B - 4} textAnchor="end" className="fill-slate-500" fontSize="9">{xLabel}</text>
      <text x={L + 4} y={T + 8} className="fill-slate-500" fontSize="9">{yLabel}</text>
      {sBefore !== undefined && (
        <line x1={X(sBefore)} x2={X(sBefore)} y1={T} y2={H - B} stroke="#dc2626" strokeDasharray="3 3" opacity={0.6} />
      )}
      {sAfter !== undefined && sAfter !== sBefore && (
        <line x1={X(sAfter)} x2={X(sAfter)} y1={T} y2={H - B} stroke="#059669" strokeDasharray="3 3" opacity={0.7} />
      )}
      <path d={path(before)} fill="none" stroke="#dc2626" strokeWidth="2" />
      <path d={path(after)} fill="none" stroke="#059669" strokeWidth="2" strokeDasharray={sameCurve(before, after) ? "4 3" : undefined} />
      <circle cx={X(xBefore)} cy={Y(yB)} r="4.5" fill="#dc2626" stroke="#fff" strokeWidth="1.5" />
      <circle cx={X(xAfter)} cy={Y(yA)} r="4.5" fill="#059669" stroke="#fff" strokeWidth="1.5" />
      <g fontSize="9" className="font-mono">
        <text x={W - R} y={T + 8} textAnchor="end" fill="#dc2626">● {t.before}</text>
        <text x={W - R} y={T + 20} textAnchor="end" fill="#059669">● {t.after}</text>
      </g>
    </svg>
  );
}

function sameCurve(a: [number, number][], b: [number, number][]) {
  return a.length === b.length && a.every((p, i) => Math.abs(p[1] - b[i][1]) < 1e-6);
}

function QueueChartCard({ c }: { c: QueueChart }) {
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-slate-200 p-2.5">
      <div className="flex items-center gap-1.5 text-[11.5px] font-semibold text-slate-800">
        <Sigma size={13} /> {t.queueChartTitle}
      </div>
      <p className="truncate text-[10.5px] text-slate-500">{c.intersectionName}</p>
      <CurveChart before={c.curveBefore} after={c.curveAfter} xBefore={c.flowBefore} xAfter={c.flowAfter}
        sBefore={c.saturationSBefore} sAfter={c.saturationSAfter} yLabel="Φq [s]" xLabel="zq [veh/h]" />
      <div className="grid grid-cols-2 gap-1 font-mono text-[10.5px] text-slate-600">
        <span>zq: {fmt(c.flowBefore, 0)} → <b className={c.flowAfter < c.saturationSAfter ? "text-emerald-700" : "text-red-700"}>{fmt(c.flowAfter, 0)}</b></span>
        <span>{t.saturation}: {fmt(c.saturationSBefore, 0)} → {fmt(c.saturationSAfter, 0)}</span>
        <span>d₀ = {fmt(c.d0Sec, 1)} s</span>
        <span>α = {c.alphaSecPerVehH.toFixed(3)} s/(veh/h)</span>
      </div>
      <p className="mt-1 font-mono text-[10px] text-slate-500">Φq = d₀ if zq &lt; s ; αzq + β otherwise, β = d₀ − αs</p>
    </div>
  );
}

function BprChartCard({ c }: { c: BprChart }) {
  const { t } = useI18n();
  return (
    <div className="rounded-xl border border-slate-200 p-2.5">
      <div className="flex items-center gap-1.5 text-[11.5px] font-semibold text-slate-800">
        <Sigma size={13} /> {t.bprChartTitle}
      </div>
      <CurveChart before={c.curveBefore} after={c.curveAfter} xBefore={c.flowBefore} xAfter={c.flowAfter} yLabel="Φi [s]" xLabel="zi [veh/h]" />
      <div className="grid grid-cols-2 gap-1 font-mono text-[10.5px] text-slate-600">
        <span>t₀ = {fmt(c.t0Sec, 1)} s</span>
        <span>cap: {fmt(c.capacityBefore, 0)} → {fmt(c.capacityAfter, 0)}</span>
      </div>
      <p className="mt-1 font-mono text-[10px] text-slate-500">Φi = t₀(1 + 0,15 (z/cap)⁴)</p>
    </div>
  );
}

export default function RecommendedRoutesTabs({ sim, onHover, onFocus, onExplain }: Props) {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("green");
  const { stptRoutes, bikeRoutes, carRoutes } = sim.recommendedRoutes;
  const cc = sim.costComparison;

  const tabs: { id: Tab; label: string; icon: typeof Leaf }[] = [
    { id: "green", label: t.tabsGreen, icon: Leaf },
    { id: "car", label: t.tabsCar, icon: Car },
    { id: "math", label: t.tabsMath, icon: FlaskConical },
  ];

  const hoverProps = (h: HighlightedRoute) => ({
    onMouseEnter: () => onHover(h),
    onMouseLeave: () => onHover(null),
    onFocus: () => onHover(h),
    onBlur: () => onHover(null),
    onClick: () => onFocus(h),
  });

  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white">
      <div role="tablist" className="grid grid-cols-3 gap-0.5 border-b border-slate-100 p-1">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`flex flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-center text-[10.5px] font-medium leading-tight transition ${
              tab === id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <Icon size={13} aria-hidden />
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-2 p-2.5" role="tabpanel">
        {tab === "green" && (
          <>
            {stptRoutes.length === 0 && <p className="text-[12px] text-slate-500">{t.noGreenRoutes}</p>}
            {stptRoutes.map((r) => {
              const gain = r.oldCorridorTimeMin - r.newCorridorTimeMin;
              return (
                <button key={r.routeId} {...hoverProps(stptHighlight(r))}
                  className="w-full rounded-xl border border-slate-200 p-2.5 text-left transition hover:border-slate-300 hover:shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#005BBC]">
                  <div className="flex items-center gap-2">
                    <span className="grid h-7 min-w-[2.2rem] place-items-center rounded-md px-1.5 font-mono text-[13px] font-bold text-white" style={{ background: r.color }}>
                      {r.shortName}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[12px] font-semibold text-slate-900">{TYPE_LABEL[r.type] ?? "STPT"} → {r.headsign}</div>
                      <div className="truncate text-[10.5px] text-slate-500">{r.longName ?? `${r.stops.length} stații`}</div>
                    </div>
                    <div className="text-right font-mono text-[12px]">
                      <span className="text-slate-500">{fmt(r.oldCorridorTimeMin, 1)}</span>
                      <span className="mx-0.5 text-slate-400">→</span>
                      <b className={gain > 0.05 ? "text-[#059669]" : "text-slate-800"}>{fmt(r.newCorridorTimeMin, 1)}</b>
                      <span className="ml-0.5 text-[10px] text-slate-500">min</span>
                    </div>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] text-slate-600">
                    <Clock size={11} aria-hidden />
                    <span>{t.nextDepartures}:</span>
                    {r.nextDepartures.map((d) => (
                      <span key={d} className="rounded bg-slate-100 px-1 font-mono">{d}</span>
                    ))}
                    <span className="text-slate-400">· {r.frequencyPerHour}/h</span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    <DataProvenanceBadge label={r.departuresSource} tone={r.departuresSource.startsWith("SMTT") ? "live" : "seed"} />
                    <DataProvenanceBadge label={r.geometrySource} tone={r.geometrySource.includes("live") ? "live" : "seed"} />
                  </div>
                </button>
              );
            })}
            <div className="rounded-xl bg-slate-50 p-2.5 text-[11px] text-slate-700">
              <div className="font-semibold">{t.ticketVsParking}</div>
              <div className="mt-1 flex items-center justify-between font-mono">
                <span>🎫 {fmt(cc.stptTicketRon, 0)} lei (60 min)</span>
                <span>
                  🅿️ {cc.timparkRonTwoHours !== null ? `${fmt(cc.timparkRonTwoHours, 2)} lei` : "—"}
                  {cc.timparkZone && <span className="ml-1 text-slate-500">({cc.timparkZone})</span>}
                </span>
              </div>
              <div className="mt-1">
                <DataProvenanceBadge label={`Wallet · Timpark SMS ${cc.smsNumber}`} />
              </div>
            </div>
            {bikeRoutes.map((b) => (
              <button key={b.routeId} {...hoverProps(bikeHighlight(b))}
                className="w-full rounded-xl border border-emerald-200 bg-emerald-50/40 p-2.5 text-left transition hover:shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#005BBC]">
                <div className="flex items-center gap-2">
                  <span className="grid h-7 w-7 place-items-center rounded-md bg-[#059669] text-white"><Bike size={15} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12px] font-semibold text-slate-900">{b.name}</div>
                    <div className="font-mono text-[10.5px] text-slate-600">
                      {fmt(b.lengthKm, 2)} km · {fmt(b.timeMin, 1)} min
                    </div>
                  </div>
                  <div className="text-right font-mono text-[11px]">
                    <div className="text-slate-500">{t.protectedLane}</div>
                    <div>
                      {fmt(b.protectedPctBefore, 0)}% → <b className={b.protectedPctAfter > b.protectedPctBefore ? "text-[#059669]" : "text-slate-800"}>{fmt(b.protectedPctAfter, 0)}%</b>
                    </div>
                  </div>
                </div>
                <div className="mt-1 text-[10.5px] text-slate-600">
                  {b.iveloStationsOnRoute.length} {t.iveloStations}
                  {b.iveloStationsOnRoute.length > 0 && <span className="text-slate-400">: {b.iveloStationsOnRoute.slice(0, 3).map((s) => s.replace("i'velo — ", "")).join(", ")}{b.iveloStationsOnRoute.length > 3 ? "…" : ""}</span>}
                </div>
                <div className="mt-1"><DataProvenanceBadge label="© OpenStreetMap · Acoperire Velo Incompletă" tone="warn" /></div>
              </button>
            ))}
          </>
        )}

        {tab === "car" && (
          <>
            {carRoutes.length === 0 && <p className="text-[12px] text-slate-500">{t.noCarRoutes}</p>}
            {carRoutes.map((r) => {
              const cut = r.role === "throttled_braess_cut_through";
              const saved = r.oldTimeMin - r.newTimeMin;
              return (
                <button key={r.id} {...hoverProps(carHighlight(r))}
                  className={`w-full rounded-xl border p-2.5 text-left transition hover:shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#005BBC] ${cut ? "border-red-200 bg-red-50/40" : "border-blue-200 bg-blue-50/30"}`}>
                  <div className="flex items-center gap-2">
                    <span className={`h-0 w-7 shrink-0 border-t-[3px] ${cut ? "border-dashed border-[#dc2626]" : "border-solid border-[#2563eb]"}`} />
                    <div className="min-w-0 flex-1">
                      <div className={`text-[10px] font-semibold uppercase tracking-wide ${cut ? "text-red-700" : "text-blue-700"}`}>
                        {cut ? (r.filteredFromNavigation ? t.filtered : t.throttled) : t.arterial}
                      </div>
                      <div className="truncate text-[12px] font-semibold text-slate-900">{r.name}</div>
                      <div className="truncate text-[10.5px] text-slate-500">{r.odLabel}</div>
                    </div>
                  </div>
                  <div className="mt-1.5 grid grid-cols-3 gap-1 font-mono text-[10.5px]">
                    <span>
                      {fmt(r.oldTimeMin, 1)} → {r.filteredFromNavigation ? "—" : <b>{fmt(r.newTimeMin, 1)}</b>} min
                    </span>
                    <span className={!cut && saved > 0.01 ? "text-[#059669]" : "text-slate-600"}>
                      {!r.filteredFromNavigation && `${signed(-saved, 2)} min`}
                    </span>
                    <span className="text-right">
                      {fmt(r.oldFlowSharePct, 0)}% → <b>{fmt(r.flowSharePct, 0)}%</b>
                    </span>
                  </div>
                  <div className="mt-0.5 font-mono text-[10px] text-slate-500">
                    Δ {signed(r.deltaFlowVehH, 0)} veh/h {t.trafficAbsorbed}
                  </div>
                </button>
              );
            })}
            {sim.removedRouteIds.length > 0 && (
              <DataProvenanceBadge label={`Greedy route removal: ${sim.removedRouteIds.join(", ")}`} tone="warn" />
            )}
          </>
        )}

        {tab === "math" && (
          <>
            {sim.queueChart && <QueueChartCard c={sim.queueChart} />}
            {sim.bprChart && <BprChartCard c={sim.bprChart} />}
            <div className="rounded-xl border border-slate-200 p-2.5 font-mono text-[10.5px] leading-relaxed text-slate-700">
              <div>min F(x) = Σ φᵢ(zᵢ) + Σ φq(zq),  z = Rᵀx</div>
              <div>Y = Σ zₑ Φₑ(zₑ) = {fmt(sim.simulatedMetrics.totalSystemDelayVehMin, 0)} veh·min/h</div>
              <div>V = Y′ − Y = <b className={sim.simulatedMetrics.braessValueV < 0 ? "text-emerald-700" : "text-amber-700"}>{signed(sim.simulatedMetrics.braessValueV, 1)}</b></div>
              <div className="text-slate-500">gap {sim.simulatedMetrics.solverRelativeGap.toExponential(1)} · {sim.simulatedMetrics.solverIterations} it · {fmt(sim.simulatedMetrics.solverMs, 1)} ms</div>
            </div>
            {sim.sesizariSummary && (
              <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-2.5">
                <div className="flex items-center gap-1.5 text-[11.5px] font-semibold text-slate-800">
                  <MessageSquareWarning size={13} className="text-[#D97706]" /> {t.sesizariTitle}
                </div>
                <div className="mt-1 font-mono text-[20px] font-semibold text-[#D97706]">{sim.sesizariSummary.total}</div>
                <ul className="mt-1 space-y-0.5 text-[11px] text-slate-700">
                  {Object.entries(sim.sesizariSummary.byCategory).map(([k, v]) => (
                    <li key={k} className="flex justify-between gap-2"><span className="truncate">{k}</span><span className="font-mono">{v}</span></li>
                  ))}
                </ul>
                <div className="mt-1 flex flex-wrap gap-1 font-mono text-[10px] text-slate-500">
                  {Object.entries(sim.sesizariSummary.byStatus).map(([k, v]) => (
                    <span key={k} className="rounded bg-white px-1">{k}: {v}</span>
                  ))}
                </div>
                <div className="mt-1.5"><DataProvenanceBadge label={`Sesizări API · Anonimizat GDPR · ${sim.sesizariSummary.source ?? "live"}`} tone="gdpr" /></div>
              </div>
            )}
            <button onClick={onExplain}
              className="w-full rounded-xl bg-[#005BBC] px-3 py-2 text-[12.5px] font-semibold text-white shadow-sm hover:bg-[#004a99] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#005BBC]">
              {t.explainBraess}
            </button>
          </>
        )}
      </div>
    </section>
  );
}
