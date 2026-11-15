import { useRef } from "react";
import { Leaf, Loader2, X } from "lucide-react";
import type { PackageResponse, ScanRow } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt, signed } from "../api";

interface Props {
  rows: ScanRow[] | null;
  loading: boolean;
  stats: { tested: number; seconds: number } | null;
  demandScale: number;
  onPick: (r: ScanRow) => void;
  onClose?: () => void;
  pkg?: PackageResponse | null;
  onPickPackage?: (r: ScanRow) => void;
}

type Tone = "braess" | "cheap";
const TONE: Record<Tone, string> = { braess: "text-fuchsia-700", cheap: "text-emerald-700" };
const rowKey = (r: ScanRow) => `${r.kind}|${r.linkIds.join(",")}`;

/**
 * "Optimized ways": every busy segment closed (both ways) + −1 lane per street, ranked.
 * Same structure as the street panel: a header with a divider, then a scrolling body (App supplies the glass panel).
 */
export default function ScanCard({ rows, loading, stats, demandScale, onPick, onClose, pkg, onPickPackage }: Props) {
  const { t } = useI18n();
  const braess = (rows ?? []).filter((r) => r.braess);
  const cheap = (rows ?? []).filter((r) => r.lowRegret && !r.braess).slice(0, 6);
  // new results (another time of day) replay the rows' staggered entrance
  const version = useRef(0);
  const lastRows = useRef(rows);
  if (lastRows.current !== rows) {
    lastRows.current = rows;
    version.current += 1;
  }
  return (
    <>
      <header className="flex items-center gap-2 border-b border-slate-200/80 px-4 py-3">
        <h2 className="flex min-w-0 flex-1 items-center gap-2 text-[15px] font-bold leading-tight tracking-tight">
          <Leaf size={16} strokeWidth={2.2} className="shrink-0 text-emerald-600" aria-hidden="true" /> {t.scanTitle}
        </h2>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            title={t.close}
            aria-label={t.close}
          >
            <X size={17} />
          </button>
        )}
      </header>

      <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
        {demandScale !== 1 && <p className="text-[11px] leading-snug text-slate-500">{t.scanAtFullDemand}</p>}
        {loading && <p className="m-fade-in flex items-center gap-1.5 text-[12px] text-slate-500"><Loader2 size={13} className="animate-spin" /> {t.scanRunning}</p>}
        {rows && !loading && (
          <div key={version.current} className="space-y-5">
            {pkg?.filters && onPickPackage && <PackageSection pkg={pkg} onPick={onPickPackage} />}
            <section>
              <h3 className="text-[12.5px] font-semibold text-slate-800">{t.scanBraess}</h3>
              {braess.length === 0 ? (
                <p className="mt-1 text-[12px] text-slate-500">{t.scanNoBraess}</p>
              ) : (
                braess.map((r, i) => <Row key={rowKey(r)} r={r} i={i} tone="braess" onPick={onPick} />)
              )}
            </section>
            <section>
              <h3 className="text-[12.5px] font-semibold text-slate-800">{t.scanLowRegret}</h3>
              {cheap.map((r, i) => <Row key={rowKey(r)} r={r} i={braess.length + i} tone="cheap" onPick={onPick} />)}
            </section>
            {stats && (
              <p className="font-secondary text-[10.5px] text-slate-400">
                {stats.tested} {t.scanStats} · {fmt(stats.seconds, 1)} s · Wardrop UE (CFW)
              </p>
            )}
          </div>
        )}
      </div>
    </>
  );
}

function Row({ r, i, tone, onPick }: { r: ScanRow; i: number; tone: Tone; onPick: (r: ScanRow) => void }) {
  const { t } = useI18n();
  const removal = r.kind === "removal";
  const where = removal ? `${t.scanBothWays}` : `${t.heading[r.heading] ?? r.heading} · ${t.minusOneLane}`;
  return (
    <button onClick={() => onPick(r)}
      title={removal ? `${r.fromName} → ${r.toName}` : undefined}
      style={{ animationDelay: `${Math.min(i, 12) * 35}ms` }}
      className="m-rise-in mt-1.5 flex w-full items-center gap-2 rounded-lg border-[1.5px] border-slate-300 bg-white px-3 py-2 text-left transition hover:border-slate-400 hover:bg-slate-50 hover:shadow-sm active:scale-[0.99]">
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12.5px] text-slate-800">{r.street}</span>
        <span className="block truncate text-[11px] text-slate-500">{where}</span>
        {r.routeBraess && r.bestRouteGainPct > 0 && (
          <span className="block truncate text-[11px] text-slate-500">
            <span className={`font-secondary ${TONE[tone]}`}>−{fmt(r.bestRouteGainPct, 1)}%</span> {t.scanRouteFaster}
          </span>
        )}
      </span>
      <span className="shrink-0 text-right">
        <span className={`block font-secondary text-[12px] ${TONE[tone]}`}>{signed(r.changePct, 2)}%</span>
        {r.vehHSaved > 0.05 && <span className="block font-secondary text-[10.5px] text-slate-500">{fmt(r.vehHSaved, 1)} veh/h</span>}
      </span>
    </button>
  );
}

/** The greedy package as a scenario row: closures in linkIds, the bus lane (if any) in extraChanges. */
function packageRow(pkg: PackageResponse, withBus: boolean): ScanRow | null {
  const f = pkg.filters;
  const b = withBus ? pkg.withBus : null;
  if (!f || (withBus && !b)) return null;
  return {
    street: f.steps.map((s) => s.street).join(" + "), heading: "", linkIds: f.linkIds, mode: "closure", kind: "package",
    scope: "both", fromName: b ? `${b.street} (${b.heading})` : "", toName: "",
    changePct: b ? b.changePct : f.changePct, vehMinDelta: 0, vehHSaved: b ? b.vehHSaved : f.vehHSaved,
    braess: true, routeBraess: false, bestRouteGainPct: 0, lowRegret: false, stage: "verified", baseFlow: 0,
    at: [0, 0], extraChanges: b ? b.laneChanges : [],
  };
}

function PackageSection({ pkg, onPick }: { pkg: PackageResponse; onPick: (r: ScanRow) => void }) {
  const { t } = useI18n();
  const b = pkg.withBus;
  const items = [
    { row: packageRow(pkg, false), label: t.pkgFilters, sub: null as string | null },
    { row: packageRow(pkg, true), label: t.pkgWithBus,
      sub: b ? `${t.pkgLaneBus} ${b.street} (${t.heading[b.heading] ?? b.heading}) · ${b.busLines.join(", ")}` : null },
  ].filter((x): x is { row: ScanRow; label: string; sub: string | null } => !!x.row);
  return (
    <section>
      <h3 className="text-[12.5px] font-semibold text-slate-800">{t.pkgTitle}</h3>
      {items.map(({ row, label, sub }, i) => (
        <button key={label} onClick={() => onPick(row)} style={{ animationDelay: `${i * 35}ms` }}
          className="m-rise-in mt-1.5 flex w-full items-center gap-2 rounded-lg border-[1.5px] border-slate-300 bg-white px-3 py-2 text-left transition hover:border-slate-400 hover:bg-slate-50 hover:shadow-sm active:scale-[0.99]">
          <span className="min-w-0 flex-1">
            <span className="block text-[11px] text-slate-500">{label}</span>
            <span className="block text-[12.5px] leading-snug text-slate-800">{row.street}</span>
            {sub && <span className="block text-[11px] leading-snug text-slate-500">{sub}</span>}
          </span>
          <span className="shrink-0 text-right">
            <span className={`block font-secondary text-[12px] ${TONE.braess}`}>{signed(row.changePct, 2)}%</span>
            {row.vehHSaved > 0.05 && <span className="block font-secondary text-[10.5px] text-slate-500">{fmt(row.vehHSaved, 1)} veh/h</span>}
          </span>
        </button>
      ))}
    </section>
  );
}
