import { Clock, Gauge } from "lucide-react";
import type { Profile, ProfileMeta } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt } from "../api";
import { useSlidingThumb } from "../motion";

interface Props {
  profiles: ProfileMeta[];
  profile: Profile;
  demandScale: number;
  demandVehH: number | null;
  onChange: (p: Profile) => void;
  onDemandScale: (s: number) => void;
}

/** Bottom bar: time-of-day selector + demand level meter + where the demand comes from. */
export default function ProfileBar({ profiles, profile, demandScale, demandVehH, onChange, onDemandScale }: Props) {
  const { t, lang } = useI18n();
  const pct = Math.round(demandScale * 100);
  const thumb = useSlidingThumb(profile);
  return (
    <div className="glass pointer-events-auto flex max-w-full flex-wrap items-center justify-center gap-x-2 gap-y-1 rounded-3xl px-2 py-1.5">
      <div className="flex min-w-0 max-w-full items-center gap-1">
        <Clock size={14} className="ml-1 shrink-0 text-[#005BBC]" aria-hidden="true" />
        <div ref={thumb.ref} className="relative flex flex-wrap justify-center gap-0.5" role="radiogroup" aria-label={t.profileLabel}>
          {/* the blue pill slides to the chosen time of day */}
          <span aria-hidden="true" style={thumb.style}
            className="absolute left-0 top-0 rounded-full bg-[#005BBC] shadow-sm transition-[transform,width,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]" />
          {profiles.map((p) => {
            const on = p.id === profile;
            return (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={on}
                data-thumb-key={p.id}
                onClick={() => onChange(p.id)}
                title={`${lang === "ro" ? p.labelRo : p.labelEn} · ${p.start}–${p.end}`}
                className={`relative whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] font-semibold transition-[color,background-color,transform] duration-300 active:scale-95 ${
                  on ? "text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {lang === "ro" ? p.labelRo : p.labelEn}
                <span className={`ml-1 font-secondary text-[10.5px] font-normal ${on ? "text-white/80" : "text-slate-400"}`}>{p.start}</span>
              </button>
            );
          })}
        </div>
      </div>

      <label className="flex items-center gap-1.5 rounded-full px-1.5" title={t.demandMeterHint}>
        <Gauge size={14} className="shrink-0 text-[#005BBC]" aria-hidden="true" />
        <span className="text-[11.5px] font-semibold text-slate-600">{t.demandMeter}</span>
        <input
          type="range"
          min={50}
          max={150}
          step={5}
          value={pct}
          onChange={(e) => onDemandScale(Number(e.target.value) / 100)}
          onDoubleClick={() => onDemandScale(1)}
          aria-label={t.demandMeter}
          aria-valuetext={`${pct}%`}
          className="h-1.5 w-24 cursor-pointer accent-[#005BBC]"
        />
        <span className={`w-10 font-secondary text-[11px] font-semibold transition-colors duration-300 ${pct === 100 ? "text-slate-600" : pct > 100 ? "text-orange-700" : "text-emerald-700"}`}>
          {pct}%
        </span>
        {demandVehH !== null && (
          <span className="hidden font-secondary text-[10.5px] text-slate-500 sm:inline">{fmt(demandVehH, 0)} {t.vehH}</span>
        )}
      </label>
    </div>
  );
}
