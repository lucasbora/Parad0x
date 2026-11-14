import { useEffect } from "react";
import { Sparkles, X } from "lucide-react";
import { useI18n } from "../i18n/translations";
import { fmt } from "../api";

interface Props {
  changePct: number | null;   // negative = total time went down
  estimated: boolean;   // demand from OSM land use, not yet measured
  onClose: () => void;
}

/** Pops up when taking car capacity away LOWERS total time in traffic (Braess's paradox). */
export default function BraessToast({ changePct, estimated, onClose }: Props) {
  const { t } = useI18n();
  useEffect(() => {
    if (changePct === null) return;
    const id = window.setTimeout(onClose, 12000);
    return () => window.clearTimeout(id);
  }, [changePct, onClose]);
  if (changePct === null) return null;
  return (
    <div role="status" aria-live="polite"
      className="pointer-events-auto absolute left-1/2 top-[128px] z-40 w-[min(460px,calc(100%-32px))] -translate-x-1/2 rounded-xl border border-fuchsia-300 bg-white p-3 shadow-xl">
      <div className="flex items-start gap-2.5">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-fuchsia-100 text-fuchsia-700"><Sparkles size={17} /></span>
        <div className="flex-1">
          <p className="text-[14px] font-bold text-fuchsia-800">{t.braessTitle}</p>
          <p className="text-[12.5px] leading-snug text-slate-700">
            {t.braessBody} <b className="font-mono">{fmt(Math.abs(changePct), 2)}%</b>.
          </p>
          {estimated && <p className="mt-1 text-[11px] font-semibold text-amber-700">{t.estimatedBanner}</p>}
        </div>
        <button onClick={onClose} aria-label={t.close} className="rounded p-0.5 text-slate-400 hover:text-slate-800"><X size={15} /></button>
      </div>
    </div>
  );
}
