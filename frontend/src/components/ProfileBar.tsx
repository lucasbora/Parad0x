import { BadgeCheck, Clock, FlaskConical, Gauge } from "lucide-react";
import type { DemandSource, Profile, ProfileMeta } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt } from "../api";

interface Props {
  profiles: ProfileMeta[];
  profile: Profile;
  demandSource: DemandSource | null;
  demandScale: number;
  demandVehH: number | null;
  onChange: (p: Profile) => void;
  onDemandScale: (s: number) => void;
}

/** Bottom bar: time-of-day selector + demand level meter + where the demand comes from. */
export default function ProfileBar({ profiles, profile, demandSource, demandScale, demandVehH, onChange, onDemandScale }: Props) {
  const { t, lang } = useI18n();
  const calibrated = demandSource === "calibrated";
  const pct = Math.round(demandScale * 100);
  return (
    <div className="glass pointer-events-auto flex max-w-full flex-wrap items-center justify-center gap-x-2 gap-y-1 rounded-3xl px-2 py-1.5">
      <div className="flex items-center gap-1">
        <Clock size={14} className="ml-1 shrink-0 text-[#005BBC]" aria-hidden="true" />
        <div className="flex gap-0.5" role="radiogroup" aria-label={t.profileLabel}>
          {profiles.map((p) => {
            const on = p.id === profile;
            return (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => onChange(p.id)}
                title={`${lang === "ro" ? p.labelRo : p.labelEn} · ${p.start}–${p.end}`}
                className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[12px] font-semibold transition ${
                  on ? "bg-[#005BBC] text-white shadow-sm" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
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
        <span className={`w-10 font-secondary text-[11px] font-semibold ${pct === 100 ? "text-slate-600" : pct > 100 ? "text-orange-700" : "text-emerald-700"}`}>
          {pct}%
        </span>
        {demandVehH !== null && (
          <span className="hidden font-secondary text-[10.5px] text-slate-500 sm:inline">{fmt(demandVehH, 0)} {t.vehH}</span>
        )}
      </label>

      {demandSource && (
        <span
          title={calibrated ? t.demandCalibratedHint : t.demandEstimatedHint}
          className={`flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 font-secondary text-[10.5px] font-semibold ${
            calibrated ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-300 bg-amber-50 text-amber-800"
          }`}
        >
          {calibrated ? <BadgeCheck size={12} /> : <FlaskConical size={12} />}
          {calibrated ? t.demandCalibrated : t.demandEstimated}
        </span>
      )}
    </div>
  );
}
