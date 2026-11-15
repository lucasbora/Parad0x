import type { CorridorResponse } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt } from "../api";

/** Where the numbers come from: estimated demand, the network, the turn rules. */
export default function SourcesNote({ data }: { data: CorridorResponse }) {
  const { t } = useI18n();
  const s = data.sources;
  return (
    <div className="space-y-1 text-[11px] leading-snug text-slate-500">
      <p>{t.estimatedLine.replace("{n}", fmt(data.landUse.residents, 0))}</p>
      <p>
        <span className="font-semibold">{t.sources}:</span> {t.network}: {s.network} ({s.networkFetchedAt.slice(0, 10)}) ·{" "}
        {s.stats.links} links ({s.stats.sideStreetLinks} side streets) · {s.stats.junctions} intersections ({s.stats.signalized} signals) ·{" "}
        {s.stats.zones} land-use zones · SMTT live
      </p>
      {s.turns && (
        <p>
          <span className="font-semibold">{t.turnRules}:</span> OSM {s.turns.applied}/{s.turns.relations} ·
          U-turn {s.turns.uTurnsBanned} · {s.turns.bannedMovements} / {s.turns.bannedMovements + s.turns.allowedMovements} movements banned
        </p>
      )}
    </div>
  );
}
