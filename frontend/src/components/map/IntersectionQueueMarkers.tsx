import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { Map as MLMap } from "maplibre-gl";
import type { Feature, LngLat, QueueProps, UpdatedQueue } from "../../types/simulator";
import { useI18n } from "../../i18n/translations";

interface Props {
  map: MLMap;
  queues: Feature<{ type: "Point"; coordinates: LngLat }, QueueProps>[];
  updates: UpdatedQueue[] | null;
}

/**
 * Phantom intersection queue pillars: pulsing red badges where z_q ≥ s that
 * shrink and turn green once a lane swap resolves the Braess bottleneck.
 */
export default function IntersectionQueueMarkers({ map, queues, updates }: Props) {
  const { t } = useI18n();
  const markers = useRef(new Map<string, { marker: maplibregl.Marker; el: HTMLDivElement }>());

  useEffect(() => {
    const store = markers.current;
    return () => {
      store.forEach(({ marker }) => marker.remove());
      store.clear();
    };
  }, [map]);

  useEffect(() => {
    const upd = new Map((updates ?? []).map((u) => [u.id, u]));
    const seen = new Set<string>();
    for (const f of queues) {
      const p = f.properties;
      const u = upd.get(p.id);
      const flow = u ? u.flow : p.flow;
      const delay = u ? u.queueDelaySec : p.queueDelaySec;
      const saturated = u ? u.isSaturated : p.isSaturated;
      const wasSaturated = u ? u.wasSaturated : p.isSaturated;
      const s = u ? u.saturationS : p.saturationS;
      const resolved = wasSaturated && !saturated;
      const relieved = u ? u.queueDelaySec < u.baselineQueueDelaySec - 3 : false;
      const show = flow > 60 || wasSaturated;
      if (!show) continue;
      seen.add(p.id);
      let entry = markers.current.get(p.id);
      if (!entry) {
        const el = document.createElement("div");
        entry = { el, marker: new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(f.geometry.coordinates).addTo(map) };
        markers.current.set(p.id, entry);
      }
      const state = saturated ? (relieved ? "relieved" : "saturated") : resolved ? "resolved" : "free";
      const size = saturated ? Math.min(46, 22 + delay / 6) : 18;
      entry.el.className = `queue-pillar queue-${state}`;
      entry.el.style.setProperty("--qsize", `${size}px`);
      entry.el.title = `${p.intersectionName}\nz_q = ${Math.round(flow)} veh/h · s = ${Math.round(s)} · ${Math.round(delay)} s (${saturated ? t.saturated : t.free})`;
      entry.el.setAttribute("role", "img");
      entry.el.setAttribute("aria-label", entry.el.title);
      entry.el.innerHTML =
        `<span class="queue-ring"></span><span class="queue-core">${Math.round(delay)}<small>s</small></span>`;
    }
    markers.current.forEach((entry, id) => {
      if (!seen.has(id)) {
        entry.marker.remove();
        markers.current.delete(id);
      }
    });
  }, [map, queues, updates, t]);

  return null;
}
