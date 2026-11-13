import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, StyleSpecification } from "maplibre-gl";
import type { BusResult, CorridorResponse, SimulateOk } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt, signed } from "../api";

type GJ = Parameters<GeoJSONSource["setData"]>[0];
type LayerSpec = Parameters<MLMap["addLayer"]>[0];
const gj = (x: unknown) => x as GJ;

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#f1f5f9" } }],
};
const EMPTY = { type: "FeatureCollection", features: [] };

interface Props {
  data: CorridorResponse;
  result: SimulateOk | null;
  selectedLinkIds: string[];
  highlightBus: BusResult | null;
  onPickLink: (linkId: string) => void;
}

function muteBasemap(map: MLMap) {
  for (const l of map.getStyle().layers ?? []) {
    const id = l.id.toLowerCase();
    try {
      if (l.type === "symbol" && (id.includes("poi") || id.includes("housenumber"))) {
        map.setLayoutProperty(l.id, "visibility", "none");
      } else if (l.type === "symbol") {
        map.setPaintProperty(l.id, "text-color", "#94a3b8");
      } else if (l.type === "fill" && id.includes("building")) {
        map.setPaintProperty(l.id, "fill-opacity", 0.4);
      }
    } catch {
      /* layer without that property */
    }
  }
}

export default function CorridorMap({ data, result, selectedLinkIds, highlightBus, onPickLink }: Props) {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement | null>(null);
  const [map, setMap] = useState<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const pickRef = useRef(onPickLink);
  pickRef.current = onPickLink;
  const popup = useRef<maplibregl.Popup | null>(null);
  const tRef = useRef(t);
  tRef.current = t;

  useEffect(() => {
    if (!ref.current) return;
    const [s, w, n, e] = data.corridor.bbox;
    const m = new maplibregl.Map({
      container: ref.current,
      style: STYLE_URL,
      bounds: [[w, s], [e, n]],
      fitBoundsOptions: { padding: 40 },
      attributionControl: false,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: "© OpenStreetMap contributors · OpenFreeMap" }));
    let fellBack = false;
    m.on("error", (ev) => {
      if (!fellBack && !m.isStyleLoaded() && String(ev.error?.message ?? "").toLowerCase().includes("fetch")) {
        fellBack = true;
        m.setStyle(FALLBACK_STYLE);
      }
    });
    m.on("style.load", () => {
      muteBasemap(m);
      setup(m);
      setReady(true);
    });
    setMap(m);
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setup(m: MLMap) {
    for (const id of ["area", "links", "bus", "gates", "junctions"]) {
      if (!m.getSource(id)) m.addSource(id, { type: "geojson", data: gj(EMPTY) });
    }
    const add = (spec: Record<string, unknown>) => {
      if (!m.getLayer(spec.id as string)) m.addLayer(spec as unknown as LayerSpec);
    };
    const offset = ["interpolate", ["linear"], ["zoom"], 14, 1.5, 18, 6];
    add({ id: "area-line", type: "line", source: "area", paint: { "line-color": "#64748b", "line-width": 1.5, "line-dasharray": [3, 2] } });
    add({ id: "bus-line", type: "line", source: "bus", layout: { "line-cap": "round" },
      paint: { "line-color": ["get", "color"], "line-width": 9, "line-opacity": 0.35, "line-offset": offset } });
    add({ id: "links-casing", type: "line", source: "links", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#ffffff", "line-width": ["+", 3, ["get", "w"]], "line-offset": offset } });
    add({ id: "links-line", type: "line", source: "links", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["get", "color"], "line-width": ["get", "w"], "line-offset": offset } });
    add({ id: "links-selected", type: "line", source: "links", filter: ["==", ["get", "selected"], true],
      layout: { "line-cap": "round" },
      paint: { "line-color": "#005BBC", "line-width": ["+", 6, ["get", "w"]], "line-opacity": 0.35, "line-offset": offset } });
    add({ id: "links-hit", type: "line", source: "links", paint: { "line-color": "#000", "line-opacity": 0, "line-width": 16, "line-offset": offset } });
    add({ id: "junctions-signal", type: "circle", source: "junctions", filter: ["==", ["get", "signalized"], true],
      paint: { "circle-radius": 3.5, "circle-color": "#0f172a", "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
    add({ id: "gates-circle", type: "circle", source: "gates",
      paint: { "circle-radius": 7, "circle-color": ["case", ["get", "counted"], "#059669", "#DC2626"],
        "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });

    m.on("click", "links-hit", (ev: MapLayerMouseEvent) => {
      const id = ev.features?.[0]?.properties?.id;
      if (id) pickRef.current(String(id));
    });
    m.on("mouseenter", "links-hit", () => (m.getCanvas().style.cursor = "pointer"));
    m.on("mouseleave", "links-hit", () => {
      m.getCanvas().style.cursor = "";
      popup.current?.remove();
    });
    m.on("mousemove", "links-hit", (ev: MapLayerMouseEvent) => {
      const p = ev.features?.[0]?.properties as Record<string, unknown> | undefined;
      if (!p) return;
      const tt = tRef.current;
      const delta = Number(p.delta);
      const html =
        `<div style="font:12px Inter,sans-serif"><b>${String(p.street)}</b> · ${tt.heading[String(p.heading)] ?? p.heading}` +
        `<div style="color:#64748b">${String(p.carLanes)} ${tt.carLanesNow}</div>` +
        (p.hasResult === true
          ? `<div style="font-family:'JetBrains Mono',monospace;margin-top:2px">${fmt(Number(p.flowBefore), 0)} → ${fmt(Number(p.flowAfter), 0)} ${tt.vehH}` +
            (Math.abs(delta) >= 1 ? ` (${signed(delta, 0)})` : "") + `</div>`
          : "") +
        `</div>`;
      if (!popup.current) popup.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
      popup.current.setLngLat(ev.lngLat).setHTML(html).addTo(m);
    });
    m.on("click", "gates-circle", (ev: MapLayerMouseEvent) => {
      const p = ev.features?.[0]?.properties as Record<string, unknown> | undefined;
      if (!p) return;
      const tt = tRef.current;
      const [lng, lat] = (ev.features?.[0]?.geometry as unknown as { coordinates: [number, number] }).coordinates;
      new maplibregl.Popup({ offset: 10 })
        .setLngLat([lng, lat])
        .setHTML(
          `<div style="font:12px Inter,sans-serif"><b>${String(p.street)}</b><div style="font-family:'JetBrains Mono',monospace">${String(p.id)}</div>` +
            `<div>${tt.inLabel}: ${p.needsIn ? (p.countedIn ? `${p.inVehH} ${tt.vehH}` : "—") : "n/a"} · ${tt.outLabel}: ${p.needsOut ? (p.countedOut ? `${p.outVehH} ${tt.vehH}` : "—") : "n/a"}</div>` +
            `<a target="_blank" rel="noreferrer" href="https://maps.google.com/?q=${lat},${lng}">Google Maps ↗</a></div>`,
        )
        .addTo(m);
    });
  }

  const linksFC = useMemo(() => {
    const res = new Map((result?.links ?? []).map((l) => [l.id, l]));
    const sel = new Set(selectedLinkIds);
    const maxDelta = Math.max(50, ...(result?.links ?? []).map((l) => Math.abs(l.deltaFlow)));
    return {
      type: "FeatureCollection",
      features: data.links.features.map((f) => {
        const p = f.properties;
        const r = res.get(p.id);
        const flow = r ? r.flowAfter : 0;
        let color = p.isMainStreet ? "#334155" : "#94a3b8";
        let w = 1.5 + p.carLanes * 1.2;
        if (r) {
          w = 1.5 + Math.min(flow / 150, 10);
          const d = r.deltaFlow / maxDelta;
          color = Math.abs(r.deltaFlow) < 5 ? "#94a3b8" : d < 0 ? (d < -0.4 ? "#1d4ed8" : "#60a5fa") : d > 0.4 ? "#c2410c" : "#fb923c";
        }
        return {
          type: "Feature",
          geometry: f.geometry,
          properties: {
            id: p.id, street: p.street, heading: p.heading, carLanes: p.carLanes, color, w,
            selected: sel.has(p.id), hasResult: !!r, flowBefore: r?.flowBefore ?? 0, flowAfter: r?.flowAfter ?? 0,
            delta: r?.deltaFlow ?? 0,
          },
        };
      }),
    };
  }, [data, result, selectedLinkIds]);

  useEffect(() => {
    if (!map || !ready) return;
    const [s, w, n, e] = data.corridor.bbox;
    (map.getSource("area") as GeoJSONSource).setData(gj({
      type: "Feature", properties: {},
      geometry: { type: "LineString", coordinates: [[w, s], [e, s], [e, n], [w, n], [w, s]] },
    }));
    (map.getSource("links") as GeoJSONSource).setData(gj(linksFC));
    (map.getSource("junctions") as GeoJSONSource).setData(gj(data.junctions));
    (map.getSource("gates") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.gates.features.map((g) => ({
        ...g,
        properties: {
          ...g.properties,
          counted: (!g.properties.needsIn || g.properties.countedIn) && (!g.properties.needsOut || g.properties.countedOut),
        },
      })),
    }));
  }, [map, ready, data, linksFC]);

  useEffect(() => {
    if (!map || !ready) return;
    const ids = new Set(highlightBus?.linkIds ?? []);
    (map.getSource("bus") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.links.features
        .filter((f) => ids.has(f.properties.id))
        .map((f) => ({ ...f, properties: { color: highlightBus?.color ?? "#7c3aed" } })),
    }));
  }, [map, ready, data, highlightBus]);

  return (
    <div className="relative h-full w-full">
      <div ref={ref} className="h-full w-full" />
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-[11px] text-slate-600 shadow-sm">
        <div className="flex items-center gap-2"><span className="h-1.5 w-6 rounded bg-[#005BBC]/50" /> {t.legendSelected}</div>
        {result ? (
          <>
            <div className="flex items-center gap-2"><span className="h-1.5 w-6 rounded bg-[#1d4ed8]" /> {t.legendLess}</div>
            <div className="flex items-center gap-2"><span className="h-1.5 w-6 rounded bg-[#c2410c]" /> {t.legendMore}</div>
            <div className="text-slate-400">{t.legendFlow}</div>
          </>
        ) : null}
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#059669]" /> {t.legendGateOk}</div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#DC2626]" /> {t.legendGateMissing}</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-slate-900" /> {t.legendSignal}</div>
      </div>
    </div>
  );
}
