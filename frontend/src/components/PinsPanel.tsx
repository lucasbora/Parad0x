import { ArrowRight, MapPin, Pin as PinIcon, X } from "lucide-react";
import type { Pin } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt, signed } from "../api";

export interface PinTime {
  pin: Pin;
  beforeSec: number | null;
  afterSec: number | null;
}

interface Props {
  times: PinTime[];
  onTogglePin: (p: Pin) => void;
  onRemove: (p: Pin) => void;
}

/** Streets picked so far with their travel time; the pin button keeps a street's time on the map. */
export default function PinsPanel({ times, onTogglePin, onRemove }: Props) {
  const { t } = useI18n();
  return (
    <section>
      <h3 className="flex items-center gap-1.5 text-[12.5px] font-semibold text-slate-800">
        <MapPin size={14} className="text-[#005BBC]" /> {t.pinsTitle}
      </h3>
      {times.length === 0 && <p className="m-fade-in mt-1 text-[12px] text-slate-500">{t.noPins}</p>}
      <ul className="mt-1 divide-y divide-slate-100">
        {times.map(({ pin, beforeSec, afterSec }) => {
          const changed = beforeSec !== null && afterSec !== null && Math.abs(afterSec - beforeSec) >= 0.5;
          const d = changed ? (afterSec as number) - (beforeSec as number) : 0;
          const pinLabel = pin.onMap ? t.unpinThis : t.pinThis;
          return (
            <li key={`${pin.street}|${pin.heading}`} className="m-rise-in flex items-center gap-2 py-1.5">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12px] text-slate-800">{pin.street}</span>
                <span className="block text-[10.5px] text-slate-500">{t.heading[pin.heading] ?? pin.heading}</span>
              </span>
              {/* keyed by the times: a new value fades in */}
              <span key={`${beforeSec}|${afterSec}`} className="m-fade-in whitespace-nowrap font-secondary text-[12px]">
                {beforeSec === null ? "—" : `${fmt(beforeSec / 60, 2)}`}
                {changed && (
                  <>
                    <ArrowRight size={11} className="mx-0.5 inline text-slate-400" />
                    <b>{fmt((afterSec as number) / 60, 2)}</b>
                  </>
                )}{" "}
                {t.min}
                {changed && <span className={`ml-1 ${d < 0 ? "text-emerald-700" : "text-orange-700"}`}>({signed(d, 0)} {t.s})</span>}
              </span>
              <button
                type="button"
                onClick={() => onTogglePin(pin)}
                aria-pressed={pin.onMap}
                aria-label={pinLabel}
                title={pinLabel}
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-md transition duration-200 active:scale-90 ${
                  pin.onMap ? "bg-[#005BBC] text-white shadow-sm hover:bg-[#004a99]" : "text-slate-400 hover:bg-slate-100 hover:text-[#005BBC]"
                }`}
              >
                <PinIcon size={13} strokeWidth={2.2} className={`transition-transform duration-200 ${pin.onMap ? "rotate-0" : "rotate-45"}`}
                  fill={pin.onMap ? "currentColor" : "none"} />
              </button>
              <button onClick={() => onRemove(pin)} aria-label={t.removePin} title={t.removePin}
                className="rounded p-0.5 text-slate-400 transition hover:text-slate-800 active:scale-90">
                <X size={13} />
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
