import type { CalibrationResponse, CorridorResponse, FittedRow } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt } from "../api";

function GehTable({ rows }: { rows: (FittedRow & { label: string; title?: string })[] }) {
  const { t } = useI18n();
  return (
    <table className="mt-1 w-full text-left text-[11px]">
      <thead className="text-slate-500"><tr><th className="font-normal">—</th><th className="font-normal">{t.counted}</th><th className="font-normal">{t.model}</th><th className="font-normal">GEH</th></tr></thead>
      <tbody className="font-secondary">
        {rows.map((r, i) => (
          <tr key={i} className="border-t border-slate-100">
            <td className="max-w-[150px] truncate font-sans" title={r.title ?? r.label}>{r.label}</td>
            <td>{fmt(r.counted, 0)}</td><td>{fmt(r.model, 0)}</td>
            <td className={r.geh < 5 ? "text-emerald-700" : "text-red-700"}>{fmt(r.geh, 1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ModelCheckCard({ data, calibration }: { data: CorridorResponse; calibration: CalibrationResponse | null }) {
  const { t } = useI18n();
  const cal = calibration && calibration.status === "ok" ? calibration : null;
  const fitted = cal ? [
    ...cal.fitted.gates.map((g) => ({ ...g, label: `${g.street} (${g.direction === "in" ? t.inLabel : t.outLabel})` })),
    ...cal.fitted.links.map((l) => ({ ...l, label: l.street, title: l.linkId })),
  ] : [];
  const heldOut = !!cal && (cal.turns.length > 0 || cal.travelTimes.length > 0);

  return (
    <div className="space-y-3">
      <details className="rounded-xl border border-slate-200 bg-white p-3">
        <summary className="cursor-pointer text-[12.5px] font-semibold text-slate-800">{t.calibrationTitle}</summary>
        {!cal && <p className="mt-2 text-[12px] text-slate-600">{t.calibrationMissing}</p>}

        {cal && fitted.length > 0 && (
          <div className="mt-2">
            <p className="text-[11.5px] font-semibold text-slate-700">{t.fittedTitle}</p>
            <p className="text-[11px] text-slate-500">{t.fittedNote}</p>
            {cal.localMultiplier !== 1 && (
              <p className="mt-0.5 font-secondary text-[11px] text-slate-600">{t.localMultiplier}: ×{fmt(cal.localMultiplier, 2)}</p>
            )}
            <GehTable rows={fitted} />
          </div>
        )}

        {cal && (
          <div className="mt-3">
            <p className="text-[11.5px] font-semibold text-slate-700">{t.heldOutTitle}</p>
            {!heldOut && <p className="text-[11.5px] text-slate-500">{t.calibrationMissing}</p>}
            {cal.turns.length > 0 && (
              <>
                <p className="mt-1 text-[11.5px] text-slate-600">
                  GEH &lt; 5: <b>{cal.summary.gehUnder5}/{cal.summary.turnsCounted}</b>
                  {cal.summary.gehUnder5Pct !== null && ` (${cal.summary.gehUnder5Pct}%)`} · {t.gehHint}
                </p>
                <GehTable rows={cal.turns.map((r) => ({ ...r, street: r.from, label: `${r.from} → ${r.to}`, title: `${r.intersection}: ${r.from} → ${r.to}` }))} />
              </>
            )}
            {cal.travelTimes.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-[11.5px]">
                {cal.travelTimes.map((r) => (
                  <li key={r.route}>{r.route}: {t.observed} <span className="font-secondary">{fmt(r.observedMin, 1)}</span> · {t.model} <span className="font-secondary">{fmt(r.modelMin, 1)}</span> {t.min} ({r.diffPct > 0 ? "+" : ""}{fmt(r.diffPct, 0)}%)</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </details>

      <details className="rounded-xl border border-slate-200 bg-white p-3">
        <summary className="cursor-pointer text-[12.5px] font-semibold text-slate-800">{t.assumptionsTitle}</summary>
        <ul className="mt-2 space-y-1.5">
          {data.assumptions.map((a) => (
            <li key={a.what} className="text-[11.5px] leading-snug">
              <span className="font-medium text-slate-800">{a.what}:</span> <span className="font-secondary text-slate-700">{a.value}</span>
              <span className="block text-slate-500">{a.appliesTo} → {a.replaceWith}</span>
            </li>
          ))}
        </ul>
      </details>

      <div className="text-[11px] text-slate-500">
        <span className="font-semibold">{t.sources}:</span> {t.network}: {data.sources.network} ({data.sources.networkFetchedAt.slice(0, 10)}) ·{" "}
        {data.sources.stats.links} links ({data.sources.stats.sideStreetLinks} side streets) · {data.sources.stats.junctions} intersections ({data.sources.stats.signalized} signals) ·{" "}
        {data.sources.stats.zones} land-use zones · SMTT live
      </div>
      {data.sources.turns && (
        <div className="text-[11px] text-slate-500">
          <span className="font-semibold">{t.turnRules}:</span> OSM {data.sources.turns.applied}/{data.sources.turns.relations} ·
          U-turn {data.sources.turns.uTurnsBanned} · {data.sources.turns.bannedMovements} / {data.sources.turns.bannedMovements + data.sources.turns.allowedMovements} movements banned
        </div>
      )}
    </div>
  );
}
