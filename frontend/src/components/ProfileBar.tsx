import { BadgeCheck, Clock, FlaskConical } from "lucide-react";
import type { DemandSource, Profile, ProfileMeta } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  profiles: ProfileMeta[];
  profile: Profile;
  demandSource: DemandSource | null;
  onChange: (p: Profile) => void;
}

/** Floating time-of-day selector under the header + where the demand comes from. */
export default function ProfileBar({ profiles, profile, demandSource, onChange }: Props) {
  const { t, lang } = useI18n();
  const calibrated = demandSource === "calibrated";
  return (
    <div className="glass pointer-events-auto absolute left-1/2 top-[78px] z-20 flex max-w-[calc(100vw-24px)] -translate-x-1/2 items-center gap-1.5 rounded-full px-2 py-1.5">
      <Clock size={14} className="ml-1 shrink-0 text-[#005BBC]" aria-hidden="true" />
      <div className="flex gap-0.5 overflow-x-auto" role="radiogroup" aria-label={t.profileLabel}>
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
              <span className={`ml-1 font-mono text-[10.5px] font-normal ${on ? "text-white/80" : "text-slate-400"}`}>{p.start}</span>
            </button>
          );
        })}
      </div>
      {demandSource && (
        <span
          title={calibrated ? t.demandCalibratedHint : t.demandEstimatedHint}
          className={`flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10.5px] font-semibold ${
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
