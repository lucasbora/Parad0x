import { Leaf, Loader2, X } from "lucide-react";
import type { DemandSource, ScanRow } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt, signed } from "../api";

interface Props {
  rows: ScanRow[] | null;
  loading: boolean;
  demandSource: DemandSource | null;
  stats: { tested: number; seconds: number } | null;
  demandScale: number;
  onPick: (r: ScanRow) => void;
  onClose?: () => void;
}

const rowKey = (r: ScanRow) => `${r.kind}|${r.linkIds.join(",")}`;

/** "Where is a green lane worth it?" — every busy segment closed (both ways) + −1 lane per street, ranked. */
export default function ScanCard({ rows, loading, demandSource, stats, demandScale, onPick, onClose }: Props) {
  const { t } = useI18n();
  const braess = (rows ?? []).filter((r) => r.braess);
  const cheap = (rows ?? []).filter((r) => r.lowRegret && !r.braess).slice(0, 6);
  return (
    <section className="panel-shadow rounded-2xl bg-gradient-to-br from-emerald-50/95 via-white/95 to-white/95 p-3.5 backdrop-blur">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-[13.5px] font-bold text-slate-900">
          <Leaf size={15} className="text-[#059669]" /> {t.scanTitle}
        </h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            title={t.close}
            aria-label={t.close}
          >
            <X size={15} />
          </button>
        )}
      </div>
      <p className="mt-0.5 text-[11px] leading-snug text-slate-600">{t.scanBody}</p>
      {demandSource === "estimated" && (
        <p className="mt-1 inline-block rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 font-secondary text-[10px] font-semibold text-amber-800">
          {t.estimatedBanner}
        </p>
      )}
      {demandScale !== 1 && <p className="mt-1 text-[10.5px] leading-snug text-slate-500">{t.scanAtFullDemand}</p>}
      {loading && <p className="mt-2 flex items-center gap-1.5 text-[11.5px] text-slate-500"><Loader2 size={12} className="animate-spin" /> {t.scanRunning}</p>}
      {rows && !loading && (
        <div className="mt-2 space-y-2">
          <div>
            <p className="text-[11px] font-semibold text-fuchsia-700">{t.scanBraess}</p>
            {braess.length === 0 ? (
              <p className="text-[11.5px] text-slate-500">{t.scanNoBraess}</p>
            ) : (
              braess.map((r) => <Row key={rowKey(r)} r={r} onPick={onPick} />)
            )}
          </div>
          <div>
            <p className="text-[11px] font-semibold text-emerald-700">{t.scanLowRegret}</p>
            {cheap.map((r) => <Row key={rowKey(r)} r={r} onPick={onPick} />)}
          </div>
          {stats && (
            <p className="font-secondary text-[10.5px] text-slate-400">
              {stats.tested} {t.scanStats} · {fmt(stats.seconds, 1)} s · Wardrop UE (CFW)
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function Row({ r, onPick }: { r: ScanRow; onPick: (r: ScanRow) => void }) {
  const { t } = useI18n();
  const removal = r.kind === "removal";
  const where = removal ? `${t.scanBothWays}` : `${t.heading[r.heading] ?? r.heading} · ${t.minusOneLane}`;
  return (
    <button onClick={() => onPick(r)}
      title={removal ? `${r.fromName} → ${r.toName}` : undefined}
      className="mt-1 flex w-full items-center gap-2 rounded-lg border border-transparent bg-white/70 px-2 py-1.5 text-left transition hover:border-slate-200 hover:bg-white hover:shadow-sm">
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12px] text-slate-800">{r.street}</span>
        <span className="block truncate text-[10.5px] text-slate-500">{where}</span>
        {r.routeBraess && r.bestRouteGainPct > 0 && (
          <span className="block truncate text-[10.5px] text-slate-500">
            <span className="font-secondary text-fuchsia-700">−{fmt(r.bestRouteGainPct, 1)}%</span> {t.scanRouteFaster}
          </span>
        )}
      </span>
      <span className="text-right">
        <span className={`block font-secondary text-[11.5px] ${r.changePct < 0 ? "text-fuchsia-700" : "text-slate-600"}`}>{signed(r.changePct, 2)}%</span>
        {r.vehHSaved > 0.05 && <span className="block font-secondary text-[10px] text-slate-500">{fmt(r.vehHSaved, 1)} veh·h</span>}
      </span>
      <span className="text-[10.5px] font-semibold text-[#005BBC]">{t.scanApply} →</span>
    </button>
  );
}
