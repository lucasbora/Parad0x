import type { NetworkResponse, SimulateResponse } from "../../types/simulator";
import { useI18n } from "../../i18n/translations";
import DataProvenanceBadge from "../studio/DataProvenanceBadge";

interface Props {
  sim: SimulateResponse | null;
  network: NetworkResponse | null;
}

/** Route style legend + OSM attribution & completeness badge (bottom-centre). */
export default function RouteOverlayLegend({ sim, network }: Props) {
  const { t } = useI18n();
  const hasRoutes = !!sim && sim.recommendedRoutes.carRoutes.length > 0;
  return (
    <div className="pointer-events-auto flex flex-wrap items-center gap-x-3 gap-y-1 rounded-full border border-slate-200/80 bg-white/95 px-3 py-1.5 text-[11px] text-slate-600 shadow-island backdrop-blur">
      {hasRoutes && (
        <>
          <span className="flex items-center gap-1.5">
            <span className="h-0 w-6 border-t-[3px] border-dashed border-[#dc2626]" /> {t.throttled}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-[3px] w-6 rounded bg-[#2563eb]" /> {t.arterial}
          </span>
        </>
      )}
      {network && (
        <>
          <DataProvenanceBadge label={network.osm.attribution} tone="neutral" />
          <DataProvenanceBadge label={network.osm.badge} tone="warn" />
        </>
      )}
    </div>
  );
}
