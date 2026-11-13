import type { CorridorResponse } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  data: CorridorResponse;
  street: string | null;
  heading: string | null;
  onChange: (street: string | null, heading: string | null) => void;
}

export default function StreetPicker({ data, street, heading, onChange }: Props) {
  const { t } = useI18n();
  const choice = data.streets.find((s) => s.street === street) ?? null;
  const links = new Map(data.links.features.map((f) => [f.properties.id, f.properties]));
  const dir = choice?.directions.find((d) => d.heading === heading) ?? null;
  const lanes = dir ? dir.linkIds.map((id) => links.get(id)?.carLanes ?? 0) : [];
  const sources = dir ? new Set(dir.linkIds.map((id) => links.get(id)?.lanesSource ?? "")) : new Set<string>();
  const busLane = dir ? dir.linkIds.some((id) => links.get(id)?.busLane) : false;

  return (
    <section>
      <h2 className="text-[14px] font-semibold text-slate-900">{t.step1}</h2>
      <select
        className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-[13px] focus:border-[#005BBC] focus:outline-none focus:ring-2 focus:ring-[#005BBC]/20"
        value={street ?? ""}
        onChange={(e) => {
          const s = data.streets.find((x) => x.street === e.target.value);
          onChange(s ? s.street : null, s && s.directions.length === 1 ? s.directions[0].heading : null);
        }}
        aria-label={t.step1}
      >
        <option value="">{t.chooseStreet}</option>
        {data.streets.map((s) => (
          <option key={s.street} value={s.street}>
            {data.corridor.mainStreets.includes(s.street) ? "★ " : ""}{s.street}
          </option>
        ))}
      </select>
      <p className="mt-1 text-[11px] text-slate-500">{t.orClickMap}</p>

      {choice && (
        <div className="mt-2">
          <p className="text-[12px] font-medium text-slate-700">{t.direction}</p>
          <div className="mt-1 flex flex-wrap gap-1.5" role="radiogroup">
            {choice.directions.map((d) => (
              <button
                key={d.heading}
                role="radio"
                aria-checked={d.heading === heading}
                onClick={() => onChange(choice.street, d.heading)}
                className={`rounded-full border px-3 py-1 text-[12px] font-medium ${
                  d.heading === heading ? "border-[#005BBC] bg-[#005BBC] text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                {t.heading[d.heading] ?? d.heading}
              </button>
            ))}
          </div>
        </div>
      )}

      {dir && (
        <div className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-[12px] text-slate-700">
          <span className="font-mono">{dir.linkIds.length}</span> {t.segments} ·{" "}
          <span className="font-mono">{Math.min(...lanes) === Math.max(...lanes) ? lanes[0] : `${Math.min(...lanes)}–${Math.max(...lanes)}`}</span>{" "}
          {t.carLanesNow}{" "}
          <span className="text-slate-500">({sources.has("field check") ? t.fieldCheck : t.fromOsm})</span>
          {busLane && <span className="block text-emerald-700">{t.existingBusLane}</span>}
        </div>
      )}
    </section>
  );
}
