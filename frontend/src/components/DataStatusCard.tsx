import { useState } from "react";
import { BadgeCheck, CheckCircle2, ChevronDown, ChevronUp, Circle, ExternalLink, FlaskConical } from "lucide-react";
import type { CorridorResponse, DemandSummary, Profile } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt } from "../api";

interface Props {
  data: CorridorResponse;
  profile: Profile;
  demand: DemandSummary | null;
}

/** Where the demand comes from (OSM land use or counts) and which field data exists, per time window. */
export default function DataStatusCard({ data, profile, demand }: Props) {
  const { t, lang } = useI18n();
  const st = data.dataStatus;
  const ps = st.profiles[profile];
  const calibrated = !!ps?.calibrated;
  const meta = data.profiles.find((p) => p.id === profile);
  const lu = data.landUse;
  const [open, setOpen] = useState(false);
  const [gatesOpen, setGatesOpen] = useState(false);

  return (
    <section className={`rounded-xl border p-3 ${calibrated ? "border-emerald-200 bg-emerald-50" : "border-amber-300 bg-amber-50"}`}>
      <button className="flex w-full items-start gap-2 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {calibrated
          ? <BadgeCheck size={18} className="mt-0.5 shrink-0 text-emerald-600" />
          : <FlaskConical size={18} className="mt-0.5 shrink-0 text-amber-600" />}
        <span className="flex-1">
          <span className="block text-[13px] font-semibold text-slate-900">
            {calibrated ? t.dataReady : t.dataMissing}
            {meta && <span className="ml-1 font-mono text-[11px] font-normal text-slate-500">{lang === "ro" ? meta.labelRo : meta.labelEn} {meta.start}–{meta.end}</span>}
          </span>
          {demand && (
            <span className="block font-mono text-[11px] text-slate-600">
              {fmt(demand.totalVehH, 0)} {t.carsPerHour} · {t.throughTraffic} {fmt(demand.throughVehH, 0)}
            </span>
          )}
          <span className="block font-mono text-[11px] text-slate-600">
            {ps?.gatesCounted ?? 0}/{st.gatesTotal} {t.gatesCounted}
          </span>
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div className="mt-2 space-y-2.5">
          <p className="text-[12px] leading-relaxed text-slate-700">{t.dataMissingBody}</p>

          <div className="rounded-lg bg-white/70 p-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{t.landUseTitle}</p>
            <p className="mt-0.5 font-mono text-[11.5px] text-slate-700">
              ≈ {fmt(lu.residents, 0)} {t.residents} · {fmt(lu.buildings, 0)} {t.buildings} · {fmt(lu.pois, 0)} {t.pois} · {lu.zones} {t.zones}
            </p>
            <p className="mt-0.5 text-[10.5px] text-slate-500">© OpenStreetMap contributors (ODbL)</p>
          </div>

          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{t.profilesStatus}</p>
            <table className="mt-1 w-full text-left text-[11px]">
              <thead className="text-slate-500">
                <tr>
                  <th className="font-normal" />
                  <th className="font-normal">{t.countsGates}</th>
                  <th className="font-normal">{t.countsLinks}</th>
                  <th className="font-normal">{t.countsTurns}</th>
                  <th className="font-normal">{t.countsTimes}</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {data.profiles.map((p) => {
                  const s = st.profiles[p.id];
                  return (
                    <tr key={p.id} className={`border-t border-slate-200 ${p.id === profile ? "font-semibold text-slate-900" : "text-slate-600"}`}>
                      <td className="py-0.5 font-sans">
                        {s?.calibrated ? "✓ " : ""}{lang === "ro" ? p.labelRo : p.labelEn}
                      </td>
                      <td>{s?.gatesCounted ?? 0}/{st.gatesTotal}</td>
                      <td>{s?.linkCounts ?? 0}</td>
                      <td>{s?.turnCounts ?? 0}</td>
                      <td>{s?.travelTimes ?? 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <ul className="space-y-1">
            {st.files.map((f) => (
              <li key={f.file} className="flex items-start gap-2 text-[12px]">
                {f.present ? <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-600" /> : <Circle size={14} className="mt-0.5 shrink-0 text-slate-400" />}
                <span>
                  <span className="font-mono text-[11.5px] text-slate-900">{f.file}</span>{" "}
                  <span className="text-[10.5px] font-medium text-slate-500">
                    ({t.optional}{f.present ? ` · ${f.rows}` : ""})
                  </span>
                  <span className="block text-[11px] leading-snug text-slate-600">{t.filePurpose[f.file] ?? f.purpose}</span>
                </span>
              </li>
            ))}
          </ul>
          {st.warnings.map((w) => (
            <p key={w} className="rounded-md bg-white/70 px-2 py-1 text-[11px] text-amber-800">{w}</p>
          ))}
          <button className="flex items-center gap-1 text-[12px] font-semibold text-[#005BBC]" onClick={() => setGatesOpen((o) => !o)}>
            {t.showGates} {gatesOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          {gatesOpen && (
            <div>
              <p className="mb-1 text-[11px] text-slate-600">{t.gatesHint} {meta ? `${meta.start}–${meta.end}` : ""}.</p>
              <ul className="space-y-0.5">
                {data.gates.features.map((g) => {
                  const p = g.properties;
                  const [lng, lat] = g.geometry.coordinates;
                  const done = (p.countedProfiles ?? []).includes(profile);
                  return (
                    <li key={p.id} className="flex items-center gap-2 text-[11.5px]">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${done ? "bg-emerald-600" : "bg-red-600"}`} />
                      <span className="w-4 font-mono text-slate-500">{p.side}</span>
                      <span className="flex-1 truncate" title={p.street}>{p.street}</span>
                      <span className="font-mono text-[10.5px] text-slate-500">
                        {[p.needsIn && t.inLabel, p.needsOut && t.outLabel].filter(Boolean).join("+")}
                      </span>
                      <a className="text-[#005BBC]" href={`https://maps.google.com/?q=${lat},${lng}`} target="_blank" rel="noreferrer" aria-label={`${p.street} ${t.openMap}`}>
                        <ExternalLink size={12} />
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
