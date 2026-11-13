import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, StyleSpecification } from "maplibre-gl";
import type { BaselineLink, BusResult, CorridorResponse, LngLat, SimulateOk } from "../types/corridor";
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
// MapLibre "animated line" dash sequence
const DASHES: number[][] = [
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
];

export interface MapPinView {
  key: string;
  label: string;
  at: LngLat;
  beforeSec: number | null;
  afterSec: number | null;
}

interface Props {
  data: CorridorResponse;
  baseline: BaselineLink[] | null;
  result: SimulateOk | null;
  showDelta: boolean;
  testData: boolean;
  selectedLinkIds: string[];
  pins: MapPinView[];
  highlightBus: BusResult | null;
  onPickLink: (linkId: string) => void;
}

/** free-flowing → congested: emerald → blue → amber → red */
function slownessColor(r: number): string {
  if (r < 1.06) return "#10b981";
  if (r < 1.18) return "#3b82f6";
  if (r < 1.45) return "#f59e0b";
  return "#ef4444";
}

function deltaColor(d: number, max: number): string {
  if (Math.abs(d) < 5) return "#cbd5e1";
  const x = d / max;
  return x < 0 ? (x < -0.35 ? "#1d4ed8" : "#60a5fa") : x > 0.35 ? "#c2410c" : "#fb923c";
}

function muteBasemap(map: MLMap) {
  for (const l of map.getStyle().layers ?? []) {
    const id = l.id.toLowerCase();
    try {
      if (l.type === "symbol" && (id.includes("poi") || id.includes("housenumber"))) map.setLayoutProperty(l.id, "visibility", "none");
      else if (l.type === "symbol") map.setPaintProperty(l.id, "text-color", "#94a3b8");
      else if (l.type === "fill" && id.includes("building")) map.setPaintProperty(l.id, "fill-opacity", 0.35);
      else if (l.type === "line" && (id.includes("road") || id.includes("highway") || id.includes("street"))) map.setPaintProperty(l.id, "line-color", "#ffffff");
    } catch {
      /* layer without that property */
    }
  }
}

export default function CorridorMap(props: Props) {
  const { data, baseline, result, showDelta, testData, selectedLinkIds, pins, highlightBus, onPickLink } = props;
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement | null>(null);
  const [map, setMap] = useState<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const pickRef = useRef(onPickLink);
  pickRef.current = onPickLink;
  const tRef = useRef(t);
  tRef.current = t;
  const popup = useRef<maplibregl.Popup | null>(null);
  const pinMarkers = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (!ref.current) return;
    const [s, w, n, e] = data.corridor.bbox;
    const m = new maplibregl.Map({
      container: ref.current,
      style: STYLE_URL,
      bounds: [[w, s], [e, n]],
      fitBoundsOptions: { padding: 40 },
      pitch: 0,
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
    const offset = ["interpolate", ["linear"], ["zoom"], 14, 2, 18, 7];
    add({ id: "area-line", type: "line", source: "area", paint: { "line-color": "#94a3b8", "line-width": 1.2, "line-dasharray": [3, 2] } });
    add({ id: "bus-line", type: "line", source: "bus", layout: { "line-cap": "round" },
      paint: { "line-color": ["get", "color"], "line-width": ["+", 10, ["get", "w"]], "line-opacity": 0.3, "line-offset": offset } });
    add({ id: "links-casing", type: "line", source: "links", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#ffffff", "line-width": ["+", 3, ["get", "w"]], "line-offset": offset } });
    add({ id: "links-line", type: "line", source: "links", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["get", "color"], "line-width": ["get", "w"], "line-offset": offset } });
    add({ id: "links-flow", type: "line", source: "links", filter: [">", ["get", "flow"], 80],
      paint: { "line-color": "rgba(255,255,255,0.85)", "line-width": ["interpolate", ["linear"], ["zoom"], 14, 1, 18, 2.2],
        "line-offset": offset, "line-dasharray": DASHES[0] } });
    add({ id: "links-selected", type: "line", source: "links", filter: ["==", ["get", "selected"], true],
      layout: { "line-cap": "round" },
      paint: { "line-color": "#005BBC", "line-width": ["+", 8, ["get", "w"]], "line-opacity": 0.3, "line-offset": offset } });
    add({ id: "links-hit", type: "line", source: "links", paint: { "line-color": "#000", "line-opacity": 0, "line-width": 16, "line-offset": offset } });
    add({ id: "junctions-signal", type: "circle", source: "junctions", filter: ["==", ["get", "signalized"], true],
      paint: { "circle-radius": 3, "circle-color": "#0f172a", "circle-stroke-color": "#fff", "circle-stroke-width": 1.2 } });
    add({ id: "gates-circle", type: "circle", source: "gates",
      paint: { "circle-radius": 6, "circle-color": ["case", ["get", "counted"], "#059669", "#DC2626"],
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
      const d = Number(p.delta);
      const html =
        `<div style="font:12px Inter,sans-serif"><b>${String(p.street)}</b> · ${tt.heading[String(p.heading)] ?? p.heading}` +
        `<div style="color:#64748b">${String(p.carLanes)} ${tt.carLanesNow}</div>` +
        (p.hasFlow === true
          ? `<div style="font-family:'JetBrains Mono',monospace;margin-top:2px">${fmt(Number(p.flow), 0)} ${tt.vehH} · ${fmt(Number(p.timeSec), 0)} ${tt.s}` +
            (Math.abs(d) >= 1 ? `<br/>Δ ${signed(d, 0)} ${tt.vehH}` : "") + `</div>`
          : "") +
        `</div>`;
      if (!popup.current) popup.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
      popup.current.setLngLat(ev.lngLat).setHTML(html).addTo(m);
    });
  }

  // street colours: congestion (after the change if there is one) or before/after difference
  const linksFC = useMemo(() => {
    const base = new Map((baseline ?? []).map((l) => [l.id, l]));
    const res = new Map((result?.links ?? []).map((l) => [l.id, l]));
    const sel = new Set(selectedLinkIds);
    const maxDelta = Math.max(40, ...(result?.links ?? []).map((l) => Math.abs(l.deltaFlow)));
    return {
      type: "FeatureCollection",
      features: data.links.features.map((f) => {
        const p = f.properties;
        const r = res.get(p.id);
        const b = base.get(p.id);
        const flow = r ? r.flowAfter : b ? b.flow : 0;
        const time = r ? r.timeAfterSec : b ? b.timeSec : 0;
        const free = r ? r.freeTimeSec : b ? b.freeTimeSec : 0;
        const hasFlow = !!(r || b);
        let color = p.isMainStreet ? "#334155" : "#94a3b8";
        if (hasFlow) color = showDelta && r ? deltaColor(r.deltaFlow, maxDelta) : slownessColor(free > 0 ? time / free : 1);
        return {
          type: "Feature",
          geometry: f.geometry,
          properties: {
            id: p.id, street: p.street, heading: p.heading, carLanes: p.carLanes, color,
            w: hasFlow ? 2 + Math.min(flow / 130, 9) : 1.5 + p.carLanes,
            flow, timeSec: time, hasFlow, delta: r?.deltaFlow ?? 0, selected: sel.has(p.id),
          },
        };
      }),
    };
  }, [data, baseline, result, showDelta, selectedLinkIds]);

  useEffect(() => {
    if (!map || !ready) return;
    const [s, w, n, e] = data.corridor.bbox;
    (map.getSource("area") as GeoJSONSource).setData(gj({
      type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[w, s], [e, s], [e, n], [w, n], [w, s]] },
    }));
    (map.getSource("links") as GeoJSONSource).setData(gj(linksFC));
    (map.getSource("junctions") as GeoJSONSource).setData(gj(data.junctions));
    (map.getSource("gates") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.gates.features.map((g) => ({
        ...g,
        properties: { ...g.properties, counted: (!g.properties.needsIn || g.properties.countedIn) && (!g.properties.needsOut || g.properties.countedOut) },
      })),
    }));
  }, [map, ready, data, linksFC]);

  useEffect(() => {
    if (!map || !ready) return;
    const ids = new Set(highlightBus?.linkIds ?? []);
    (map.getSource("bus") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.links.features.filter((f) => ids.has(f.properties.id))
        .map((f) => ({ ...f, properties: { color: highlightBus?.color ?? "#7c3aed", w: 2 } })),
    }));
  }, [map, ready, data, highlightBus]);

  // pins with live travel time
  useEffect(() => {
    if (!map || !ready) return;
    pinMarkers.current.forEach((mk) => mk.remove());
    pinMarkers.current = pins.map((p) => {
      const el = document.createElement("div");
      const changed = p.beforeSec !== null && p.afterSec !== null && Math.abs(p.afterSec - p.beforeSec) >= 0.5;
      const faster = changed && (p.afterSec as number) < (p.beforeSec as number);
      el.className = "tmbg-pin";
      el.innerHTML =
        `<div class="tmbg-pin-card ${changed ? (faster ? "tmbg-pin-faster" : "tmbg-pin-slower") : ""}">` +
        `<div class="tmbg-pin-title">${p.label}</div>` +
        `<div class="tmbg-pin-time">⏱ ${p.beforeSec === null ? "—" : fmt(p.beforeSec / 60, 2)}` +
        (changed ? ` → <b>${fmt((p.afterSec as number) / 60, 2)}</b>` : "") + ` min</div></div><div class="tmbg-pin-stem"></div>`;
      return new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(p.at).addTo(map);
    });
  }, [map, ready, pins]);

  // flow animation
  useEffect(() => {
    if (!map || !ready) return;
    let raf = 0;
    let last = 0;
    const tick = (ts: number) => {
      if (ts - last > 60 && map.getLayer("links-flow")) {
        last = ts;
        map.setPaintProperty("links-flow", "line-dasharray", DASHES[Math.floor(ts / 60) % DASHES.length]);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [map, ready]);

  return (
    <div className="relative h-full w-full">
      <div ref={ref} className="h-full w-full" />
      {testData && (
        <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-full border border-amber-300 bg-amber-50/95 px-3 py-1 text-[11.5px] font-semibold text-amber-800 shadow">
          {t.testBanner}
        </div>
      )}
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-[11px] text-slate-600 shadow-sm">
        {showDelta && result ? (
          <>
            <div className="h-2 w-40 rounded-full" style={{ background: "linear-gradient(90deg,#1d4ed8,#60a5fa,#cbd5e1,#fb923c,#c2410c)" }} />
            <div className="mt-0.5 flex justify-between"><span>{t.legendLess}</span><span>{t.legendMore}</span></div>
          </>
        ) : (
          <>
            <div className="h-2 w-40 rounded-full" style={{ background: "linear-gradient(90deg,#10b981,#3b82f6,#f59e0b,#ef4444)" }} />
            <div className="mt-0.5 flex justify-between"><span>{t.legendFast}</span><span>{t.legendSlow}</span></div>
          </>
        )}
        <div className="text-slate-400">{t.legendFlow}</div>
        <div className="mt-1 flex items-center gap-3">
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-[#059669]" />{t.legendGateOk}</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-[#DC2626]" />{t.legendGateMissing}</span>
        </div>
      </div>
    </div>
  );
}
