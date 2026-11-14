import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, StyleSpecification } from "maplibre-gl";
import type { BaselineLink, BusResult, CorridorResponse, Highlight, LngLat, MapLayers, ScanRow, SimulateOk } from "../types/corridor";
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
  baselineJunctions: { nodeId: string; delaySec: number }[] | null;
  result: SimulateOk | null;
  scanRows: ScanRow[] | null;
  layers: MapLayers;
  showDelta: boolean;
  testData: boolean;
  selectedLinkIds: string[];
  pins: MapPinView[];
  highlight: Highlight | null;
  focusKey: number;
  highlightBus: BusResult | null;
  onPickLink: (linkId: string) => void;
}

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

/** Mute positron so the simulated network has maximum contrast; add 3D buildings. */
function styleBasemap(map: MLMap) {
  const style = map.getStyle();
  for (const l of style.layers ?? []) {
    const id = l.id.toLowerCase();
    try {
      if (l.type === "fill") {
        if (id.includes("building")) map.setPaintProperty(l.id, "fill-opacity", 0.25);
        else if (id.includes("water")) map.setPaintProperty(l.id, "fill-color", "#dbe4ee");
        else if (id.includes("park") || id.includes("landuse") || id.includes("landcover") || id.includes("wood")) {
          map.setPaintProperty(l.id, "fill-color", "#eef2f6");
        }
      } else if (l.type === "line" && /road|highway|street|bridge|tunnel/.test(id)) {
        map.setPaintProperty(l.id, "line-color", id.includes("casing") ? "#e2e8f0" : "#ffffff");
      } else if (l.type === "symbol") {
        if (id.includes("poi") || id.includes("housenumber")) map.setLayoutProperty(l.id, "visibility", "none");
        else map.setPaintProperty(l.id, "text-color", "#94a3b8");
      } else if (l.type === "background") {
        map.setPaintProperty(l.id, "background-color", "#f1f5f9");
      }
    } catch {
      /* layer without that property */
    }
  }
  const src = Object.entries(style.sources ?? {}).find(([, s]) => (s as { type?: string }).type === "vector")?.[0];
  if (src && !map.getLayer("tmbg-buildings-3d")) {
    try {
      map.addLayer({
        id: "tmbg-buildings-3d",
        type: "fill-extrusion",
        source: src,
        "source-layer": "building",
        minzoom: 14,
        paint: {
          "fill-extrusion-color": "#e2e8f0",
          "fill-extrusion-height": ["coalesce", ["get", "render_height"], 10],
          "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
          "fill-extrusion-opacity": 0.55,
        },
      } as unknown as LayerSpec);
    } catch {
      /* style has no building source-layer */
    }
  }
}

export default function CorridorMap(props: Props) {
  const {
    data, baseline, baselineJunctions, result, scanRows, layers, showDelta, testData, selectedLinkIds, pins,
    highlight, focusKey, highlightBus, onPickLink,
  } = props;
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
  const hlMarkers = useRef<maplibregl.Marker[]>([]);
  const junctionMarkers = useRef(new Map<string, { marker: maplibregl.Marker; el: HTMLDivElement }>());

  // ---------------------------------------------------------------- init
  useEffect(() => {
    if (!ref.current) return;
    const [s, w, n, e] = data.corridor.bbox;
    const m = new maplibregl.Map({
      container: ref.current,
      style: STYLE_URL,
      center: [(w + e) / 2 - 0.004, (s + n) / 2],
      zoom: 15,
      pitch: 42,
      bearing: -12,
      maxPitch: 70,
      attributionControl: false,
    });
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    m.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: "© OpenStreetMap contributors · OpenFreeMap · SMTT" }), "bottom-right");
    let fellBack = false;
    m.on("error", (ev) => {
      if (!fellBack && !m.isStyleLoaded() && String(ev.error?.message ?? "").toLowerCase().includes("fetch")) {
        fellBack = true;
        m.setStyle(FALLBACK_STYLE);
      }
    });
    let framed = false;
    m.on("style.load", () => {
      styleBasemap(m);
      setup(m);
      if (!framed) {
        framed = true;
        // keep the corridor clear of the floating sidebar on the left
        const narrow = window.innerWidth < 768;
        m.fitBounds([[w, s], [e, n]], {
          padding: narrow ? 30 : { top: 70, bottom: 70, left: 450, right: 70 },
          pitch: 42, bearing: -12, duration: 0,
        });
      }
      setReady(true);
    });
    setMap(m);
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setup(m: MLMap) {
    for (const id of ["area", "links", "glow", "bus", "gates", "highlight"]) {
      if (!m.getSource(id)) m.addSource(id, { type: "geojson", data: gj(EMPTY) });
    }
    const add = (spec: Record<string, unknown>) => {
      if (!m.getLayer(spec.id as string)) m.addLayer(spec as unknown as LayerSpec);
    };
    const offset = ["interpolate", ["linear"], ["zoom"], 14, 2, 18, 7];
    add({ id: "area-line", type: "line", source: "area", paint: { "line-color": "#94a3b8", "line-width": 1.2, "line-dasharray": [3, 2] } });
    // glow: emerald = low-regret, magenta = Braess
    add({ id: "glow-halo", type: "line", source: "glow", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["case", ["get", "braess"], "#d946ef", "#10b981"], "line-width": ["interpolate", ["linear"], ["zoom"], 14, 12, 18, 30],
        "line-blur": 8, "line-opacity": 0.45, "line-offset": offset } });
    add({ id: "bus-line", type: "line", source: "bus", layout: { "line-cap": "round" },
      paint: { "line-color": ["get", "color"], "line-width": 14, "line-opacity": 0.35, "line-offset": offset } });
    add({ id: "links-casing", type: "line", source: "links", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#ffffff", "line-width": ["+", 3, ["get", "w"]], "line-offset": offset } });
    add({ id: "links-line", type: "line", source: "links", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["get", "color"], "line-width": ["get", "w"], "line-offset": offset } });
    add({ id: "glow-casing", type: "line", source: "glow", filter: ["==", ["get", "braess"], true],
      paint: { "line-color": "#d946ef", "line-width": 1.2, "line-gap-width": 10, "line-offset": offset } });
    add({ id: "links-flow", type: "line", source: "links", filter: [">", ["get", "flow"], 80],
      paint: { "line-color": "rgba(255,255,255,0.85)", "line-width": ["interpolate", ["linear"], ["zoom"], 14, 1, 18, 2.4],
        "line-offset": offset, "line-dasharray": DASHES[0] } });
    add({ id: "links-selected", type: "line", source: "links", filter: ["==", ["get", "selected"], true],
      layout: { "line-cap": "round" },
      paint: { "line-color": "#005BBC", "line-width": ["+", 9, ["get", "w"]], "line-opacity": 0.3, "line-offset": offset } });
    add({ id: "hl-ghost", type: "line", source: "highlight", filter: ["==", ["get", "kind"], "ghost"],
      paint: { "line-color": "#64748b", "line-width": 4, "line-dasharray": [1.2, 1.2], "line-opacity": 0.8 } });
    add({ id: "hl-casing", type: "line", source: "highlight", filter: ["==", ["get", "kind"], "main"],
      layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#ffffff", "line-width": 11 } });
    add({ id: "hl-line", type: "line", source: "highlight", filter: ["==", ["get", "kind"], "main"],
      layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": ["get", "color"], "line-width": 6 } });
    add({ id: "links-hit", type: "line", source: "links", paint: { "line-color": "#000", "line-opacity": 0, "line-width": 16, "line-offset": offset } });
    add({ id: "gates-circle", type: "circle", source: "gates",
      paint: { "circle-radius": 6, "circle-color": ["case", ["get", "counted"], "#059669", "#DC2626"],
        "circle-stroke-color": "#fff", "circle-stroke-width": 2, "circle-pitch-alignment": "map" } });

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
        `<div class="text-[12px] leading-snug"><div class="font-semibold text-slate-900">${String(p.street)}</div>` +
        `<div class="text-slate-500">${tt.heading[String(p.heading)] ?? p.heading} · ${String(p.carLanes)} ${tt.carLanesNow}</div>` +
        (p.hasFlow === true
          ? `<div class="mt-1 font-mono text-[11px] text-slate-700">${fmt(Number(p.flow), 0)} ${tt.vehH} · ${fmt(Number(p.timeSec), 0)} ${tt.s}` +
            (Math.abs(d) >= 1 ? `<br/>Δ ${signed(d, 0)} ${tt.vehH}` : "") + `</div>`
          : "") +
        `</div>`;
      if (!popup.current) popup.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: "280px" });
      popup.current.setLngLat(ev.lngLat).setHTML(html).addTo(m);
    });
  }

  // ---------------------------------------------------------------- streets
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

  const glowFC = useMemo(() => {
    const flag = new Map<string, boolean>();
    for (const r of scanRows ?? []) {
      if (r.braess || r.lowRegret) r.linkIds.forEach((id) => flag.set(id, r.braess || flag.get(id) === true));
    }
    return {
      type: "FeatureCollection",
      features: data.links.features.filter((f) => flag.has(f.properties.id))
        .map((f) => ({ type: "Feature", geometry: f.geometry, properties: { braess: flag.get(f.properties.id) } })),
    };
  }, [data, scanRows]);

  useEffect(() => {
    if (!map || !ready) return;
    const [s, w, n, e] = data.corridor.bbox;
    (map.getSource("area") as GeoJSONSource).setData(gj({
      type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[w, s], [e, s], [e, n], [w, n], [w, s]] },
    }));
    (map.getSource("links") as GeoJSONSource).setData(gj(linksFC));
    (map.getSource("glow") as GeoJSONSource).setData(gj(glowFC));
    (map.getSource("gates") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.gates.features.map((g) => ({
        ...g,
        properties: { ...g.properties, counted: (!g.properties.needsIn || g.properties.countedIn) && (!g.properties.needsOut || g.properties.countedOut) },
      })),
    }));
  }, [map, ready, data, linksFC, glowFC]);

  useEffect(() => {
    if (!map || !ready) return;
    const ids = new Set(highlightBus?.linkIds ?? []);
    (map.getSource("bus") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.links.features.filter((f) => ids.has(f.properties.id))
        .map((f) => ({ ...f, properties: { color: highlightBus?.color ?? "#7c3aed" } })),
    }));
  }, [map, ready, data, highlightBus]);

  // ---------------------------------------------------------------- layer visibility
  useEffect(() => {
    if (!map || !ready) return;
    const vis = (ids: string[], on: boolean) =>
      ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    vis(["links-casing", "links-line"], layers.traffic);
    vis(["links-flow"], layers.traffic && layers.flow);
    vis(["glow-halo", "glow-casing"], layers.glow);
    vis(["gates-circle"], layers.gates);
    vis(["tmbg-buildings-3d"], layers.buildings3d);
  }, [map, ready, layers]);

  // ---------------------------------------------------------------- pulsing intersection markers
  useEffect(() => {
    if (!map || !ready) return;
    const store = junctionMarkers.current;
    const before = new Map((baselineJunctions ?? []).map((j) => [j.nodeId, j.delaySec]));
    const res = new Map((result?.junctions ?? []).map((j) => [j.nodeId, j]));
    const seen = new Set<string>();
    if (layers.intersections) {
      for (const f of data.junctions.features) {
        const p = f.properties;
        if (!p.signalized) continue;
        const r = res.get(p.id);
        const was = r ? r.delayBeforeSec : before.get(p.id);
        const now = r ? r.delayAfterSec : was;
        if (was === undefined || now === undefined || Math.max(was, now) < 3) continue;
        seen.add(p.id);
        let entry = store.get(p.id);
        if (!entry) {
          const el = document.createElement("div");
          entry = { el, marker: new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat(f.geometry.coordinates).addTo(map) };
          store.set(p.id, entry);
        }
        const relieved = r && now < was - 3;
        const worse = r && now > was + 3;
        // the base red-light wait (~14 s at a 90 s cycle) is normal; only queueing on top of it glows
        const state = now >= 35 ? "saturated" : now >= 20 ? "busy" : "free";
        entry.el.className = `maplibregl-marker queue-pillar queue-${relieved ? "resolved" : state}${worse ? " queue-worse" : ""}`;
        entry.el.style.setProperty("--qsize", `${Math.min(44, 16 + now / 2)}px`);
        entry.el.title = `${p.name}\n${fmt(was, 0)} s → ${fmt(now, 0)} s`;
        entry.el.innerHTML = `<span class="queue-ring"></span><span class="queue-core">${Math.round(now)}<small>s</small></span>`;
      }
    }
    store.forEach((entry, id) => {
      if (!seen.has(id)) {
        entry.marker.remove();
        store.delete(id);
      }
    });
  }, [map, ready, data, baselineJunctions, result, layers.intersections]);

  useEffect(() => {
    const store = junctionMarkers.current;
    return () => {
      store.forEach((e) => e.marker.remove());
      store.clear();
    };
  }, []);

  // ---------------------------------------------------------------- travel-time pins
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
        `<div class="tmbg-pin-time">${p.beforeSec === null ? "—" : fmt(p.beforeSec / 60, 2)}` +
        (changed ? ` → <b>${fmt((p.afterSec as number) / 60, 2)}</b>` : "") + ` min</div></div><div class="tmbg-pin-stem"></div>`;
      return new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(p.at).addTo(map);
    });
  }, [map, ready, pins]);

  // ---------------------------------------------------------------- highlighted route + A/B pins
  useEffect(() => {
    if (!map || !ready) return;
    hlMarkers.current.forEach((mk) => mk.remove());
    hlMarkers.current = [];
    const feats = [];
    if (highlight && highlight.coordinates.length >= 2) {
      feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: highlight.coordinates }, properties: { kind: "main", color: highlight.color } });
      if (highlight.ghost && highlight.ghost.length >= 2) {
        feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: highlight.ghost }, properties: { kind: "ghost" } });
      }
      const mk = (cls: string, html: string, at: LngLat, anchor: maplibregl.PositionAnchor = "center") => {
        const el = document.createElement("div");
        el.className = cls;
        el.innerHTML = html;
        hlMarkers.current.push(new maplibregl.Marker({ element: el, anchor }).setLngLat(at).addTo(map));
      };
      const c = highlight.coordinates;
      mk("route-pin route-pin-start", "A", c[0]);
      mk("route-pin route-pin-end", "B", c[c.length - 1]);
      mk("route-callout", `<span style="background:${highlight.color}"></span>${highlight.label} · <b>${highlight.time}</b>`, c[Math.floor(c.length / 2)], "bottom");
    }
    (map.getSource("highlight") as GeoJSONSource).setData(gj({ type: "FeatureCollection", features: feats }));
  }, [map, ready, highlight]);

  useEffect(() => {
    if (!map || !ready || !highlight || focusKey === 0) return;
    const b = new maplibregl.LngLatBounds();
    highlight.coordinates.forEach((c) => b.extend(c));
    map.fitBounds(b, { padding: { top: 90, bottom: 90, left: 460, right: 80 }, maxZoom: 16.5, duration: 900, pitch: 42 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusKey]);

  // ---------------------------------------------------------------- animation: flow dashes + glow pulse
  useEffect(() => {
    if (!map || !ready) return;
    let raf = 0;
    let last = 0;
    const tick = (ts: number) => {
      if (ts - last > 55) {
        last = ts;
        if (map.getLayer("links-flow")) map.setPaintProperty("links-flow", "line-dasharray", DASHES[Math.floor(ts / 55) % DASHES.length]);
        if (map.getLayer("glow-halo")) map.setPaintProperty("glow-halo", "line-opacity", 0.22 + 0.3 * (0.5 + 0.5 * Math.sin(ts / 450)));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [map, ready]);

  return (
    <div className="absolute inset-0">
      <div ref={ref} className="h-full w-full" />
      {testData && (
        <div className="pointer-events-none absolute left-1/2 top-4 -translate-x-1/2 rounded-full border border-amber-300 bg-amber-50/95 px-3 py-1 text-[11.5px] font-semibold text-amber-800 shadow-island backdrop-blur">
          {t.testBanner}
        </div>
      )}
    </div>
  );
}
