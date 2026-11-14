import { Leaf, Loader2, Sparkles, X } from "lucide-react";
import type { ScanRow } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { signed } from "../api";

interface Props {
  rows: ScanRow[] | null;
  loading: boolean;
  onPick: (r: ScanRow) => void;
  onClose?: () => void;
}

/** "Where is a green lane worth it?" — every street, one lane removed, ranked. */
export default function ScanCard({ rows, loading, onPick, onClose }: Props) {
  const { t } = useI18n();
  const braess = (rows ?? []).filter((r) => r.braess);
  const cheap = (rows ?? []).filter((r) => r.lowRegret && !r.braess).slice(0, 5);
  return (
    <section className="rounded-2xl border border-emerald-200/90 bg-gradient-to-br from-emerald-50/95 via-white/95 to-white/95 p-3.5 shadow-island backdrop-blur">
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
      {loading && <p className="mt-2 flex items-center gap-1.5 text-[11.5px] text-slate-500"><Loader2 size={12} className="animate-spin" /> {t.scanRunning}</p>}
      {rows && (
        <div className="mt-2 space-y-2">
          <div>
            <p className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-fuchsia-700"><Sparkles size={11} /> {t.scanBraess}</p>
            {braess.length === 0 ? (
              <p className="text-[11.5px] text-slate-500">{t.scanNoBraess}</p>
            ) : (
              braess.map((r) => <Row key={`${r.street}|${r.heading}`} r={r} onPick={onPick} tone="braess" />)
            )}
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">{t.scanLowRegret}</p>
            {cheap.map((r) => <Row key={`${r.street}|${r.heading}`} r={r} onPick={onPick} tone="cheap" />)}
          </div>
        </div>
      )}
    </section>
  );
}

function Row({ r, onPick, tone }: { r: ScanRow; onPick: (r: ScanRow) => void; tone: "braess" | "cheap" }) {
  const { t } = useI18n();
  return (
    <button onClick={() => onPick(r)}
      className="mt-1 flex w-full items-center gap-2 rounded-lg border border-transparent bg-white/70 px-2 py-1.5 text-left transition hover:border-slate-200 hover:bg-white hover:shadow-sm">
      <span className={`h-2 w-2 shrink-0 rounded-full ${tone === "braess" ? "bg-fuchsia-500 shadow-[0_0_6px_2px_rgba(217,70,239,.5)]" : "bg-emerald-500 shadow-[0_0_6px_2px_rgba(16,185,129,.5)]"}`} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12px] text-slate-800">{r.street}</span>
        <span className="block text-[10.5px] text-slate-500">{t.heading[r.heading] ?? r.heading} · {r.mode === "closure" ? t.closure : t.minusOneLane}</span>
      </span>
      <span className={`font-mono text-[11.5px] ${r.changePct < 0 ? "text-fuchsia-700" : "text-slate-600"}`}>{signed(r.changePct, 2)}%</span>
      <span className="text-[10.5px] font-semibold text-[#005BBC]">{t.scanApply} →</span>
    </button>
  );
}
