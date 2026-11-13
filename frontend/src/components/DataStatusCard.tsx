import { useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Circle, ExternalLink } from "lucide-react";
import type { CorridorResponse } from "../types/corridor";
import { useI18n } from "../i18n/translations";

export default function DataStatusCard({ data }: { data: CorridorResponse }) {
  const { t } = useI18n();
  const st = data.dataStatus;
  const [open, setOpen] = useState(!st.ready);
  const [gatesOpen, setGatesOpen] = useState(false);

  return (
    <section className={`rounded-xl border p-3 ${st.ready ? "border-emerald-200 bg-emerald-50" : "border-amber-300 bg-amber-50"}`}>
      <button className="flex w-full items-start gap-2 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {st.ready ? <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-600" /> : <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" />}
        <span className="flex-1">
          <span className="block text-[13px] font-semibold text-slate-900">{st.ready ? t.dataReady : t.dataMissing}</span>
          <span className="block font-mono text-[11px] text-slate-600">
            {st.gatesCounted}/{st.gatesTotal} {t.gatesCounted}
          </span>
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {!st.ready && <p className="text-[12px] leading-relaxed text-slate-700">{t.dataMissingBody}</p>}
          <ul className="space-y-1">
            {st.files.map((f) => (
              <li key={f.file} className="flex items-start gap-2 text-[12px]">
                {f.present ? <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-600" /> : <Circle size={14} className="mt-0.5 shrink-0 text-slate-400" />}
                <span>
                  <span className="font-mono text-[11.5px] text-slate-900">{f.file}</span>{" "}
                  <span className={`text-[10.5px] font-medium ${f.required ? "text-red-700" : "text-slate-500"}`}>
                    ({f.required ? t.required : t.optional}{f.present ? ` · ${f.rows}` : ""})
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
              <p className="mb-1 text-[11px] text-slate-600">{t.gatesHint}</p>
              <ul className="space-y-0.5">
                {data.gates.features.map((g) => {
                  const p = g.properties;
                  const [lng, lat] = g.geometry.coordinates;
                  const done = (!p.needsIn || p.countedIn) && (!p.needsOut || p.countedOut);
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
