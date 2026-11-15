import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, StyleSpecification } from "maplibre-gl";
import type { BaselineLink, BusResult, CorridorResponse, Highlight, LngLat, MapLayers, ScanRow, SimulateOk } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt, signed } from "../api";
import { animateEl } from "../motion";
import { TIMISOARA_BORDER_GEOJSON, TIMISOARA_MASK_GEOJSON } from "../data/timisoaraBoundary";

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

export type MapTheme = "colored" | "dark";

export interface MapPinView {
  key: string;
  label: string;
  at: LngLat;
  beforeSec: number | null;
  afterSec: number | null;
}

/** Where the camera should go. "fit" always flies there; "ensure" only moves if it is not already in view. */
export interface CameraTarget {
  coords: LngLat[];
  mode: "fit" | "ensure";
  key: number;
}

/** Screen space covered by floating panels; the camera centres things in the rest of the map. */
export interface ViewPadding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

interface Props {
  data: CorridorResponse;
  baseline: BaselineLink[] | null;
  baselineJunctions: { nodeId: string; delaySec: number }[] | null;
  result: SimulateOk | null;
  scanRows: ScanRow[] | null;
  layers: MapLayers;
  mapTheme: MapTheme;
  showDelta: boolean;
  selectedLinkIds: string[];
  pins: MapPinView[];
  highlight: Highlight | null;
  camera: CameraTarget | null;
  viewPadding: ViewPadding;
  highlightBus: BusResult | null;
  onPickLink: (linkId: string) => void;
  /** a click on the map that hits no street */
  onPickNothing: () => void;
}

const TRAFFIC_LAYERS = ["links-casing-a", "links-line-a", "links-casing-b", "links-line-b"];
const CROSSFADE_MS = 450;

/** Fade line layers in from 0 after their data changed (paint transitions only animate paint changes, not data). */
function fadeInLayers(map: MLMap, targets: Record<string, number>, ms = 350) {
  const ids = Object.keys(targets).filter((id) => map.getLayer(id));
  if (!ids.length) return;
  ids.forEach((id) => {
    map.setPaintProperty(id, "line-opacity-transition", { duration: 0, delay: 0 });
    map.setPaintProperty(id, "line-opacity", 0);
  });
  map.once("render", () => {
    ids.forEach((id) => {
      if (!map.getLayer(id)) return;
      map.setPaintProperty(id, "line-opacity-transition", { duration: ms, delay: 0 });
      map.setPaintProperty(id, "line-opacity", targets[id]);
    });
  });
  map.triggerRepaint();
}

const easeOutCubic = (k: number) => 1 - (1 - k) ** 3;

interface JunctionEntry {
  marker: maplibregl.Marker;
  el: HTMLDivElement;
  core: HTMLSpanElement;
  state: string;
  leaving?: number;
}

interface PinEntry {
  marker: maplibregl.Marker;
  el: HTMLDivElement;
  card: HTMLDivElement;
  title: HTMLDivElement;
  time: HTMLDivElement;
  timeHtml: string;
  leaving?: number;
}

const GATE_ICON = "tmbg-gate-bar";

/** Counting gate marker: a black bar with a white outline and a faint shadow, drawn across the road (2× for sharpness). */
function makeGateIcon(): ImageData {
  const r = 2;
  const W = 14 * r;
  const H = 34 * r;
  const cv = document.createElement("canvas");
  cv.width = W;
  cv.height = H;
  const ctx = cv.getContext("2d") as CanvasRenderingContext2D;
  const bar = (x: number, y: number, w: number, h: number, fill: string) => {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, w / 2);
    ctx.fillStyle = fill;
    ctx.fill();
  };
  ctx.shadowColor = "rgba(15, 23, 42, 0.35)";
  ctx.shadowBlur = 2 * r;
  ctx.shadowOffsetY = 1 * r;
  bar(3 * r, 2 * r, 8 * r, 30 * r, "#ffffff");
  ctx.shadowColor = "transparent";
  bar(5 * r, 4 * r, 4 * r, 26 * r, "#000000");
  return ctx.getImageData(0, 0, W, H);
}

/** Rotation (degrees from north) that lays the gate bar across the street the gate sits on. */
function gateRotation(data: CorridorResponse, at: LngLat, street: string): number {
  const [lng, lat] = at;
  const k = Math.cos((lat * Math.PI) / 180);
  let best = Infinity;
  let east = 1;
  let north = 0;
  // the gate sits where its street leaves the area; other streets may meet there too, so prefer its own
  const own = data.links.features.filter((f) => f.properties.street === street);
  for (const f of own.length ? own : data.links.features) {
    const c = f.geometry.coordinates;
    for (let i = 0; i < c.length; i++) {
      const d = ((c[i][0] - lng) * k) ** 2 + (c[i][1] - lat) ** 2;
      if (d < best) {
        best = d;
        const a = c[Math.max(0, i - 1)];
        const b = c[Math.min(c.length - 1, i + 1)];
        east = (b[0] - a[0]) * k;
        north = b[1] - a[1];
      }
    }
  }
  const roadBearing = (Math.atan2(east, north) * 180) / Math.PI;
  return roadBearing + 90;
}

/**
 * True when the street is already on screen in the free part of the map, so no camera move is needed.
 * Tolerant on purpose: a few points poking under a panel or past the edge (e.g. the end of a segment
 * across an intersection) do not count as "out of view".
 */
function comfortablyVisible(map: MLMap, coords: LngLat[], pad: ViewPadding): boolean {
  if (!coords.length) return true;
  const c = map.getCanvas();
  const w = c.clientWidth;
  const h = c.clientHeight;
  const inside = coords.filter((ll) => {
    const p = map.project(ll as [number, number]);
    return p.x >= pad.left && p.x <= w - pad.right && p.y >= pad.top && p.y <= h - pad.bottom;
  }).length;
  return inside / coords.length >= 0.85;
}

/** Traffic colour by how much slower than free flow: green good, yellow medium, red bad, very dark red very bad. */
function slownessColor(r: number): string {
  if (r < 1.06) return "#10b981";
  if (r < 1.18) return "#eab308";
  if (r < 1.45) return "#ef4444";
  return "#7f1d1d";
}

function deltaColor(d: number, max: number): string {
  if (Math.abs(d) < 5) return "#cbd5e1";
  const x = d / max;
  return x < 0 ? (x < -0.35 ? "#1d4ed8" : "#60a5fa") : x > 0.35 ? "#c2410c" : "#fb923c";
}

/** Style basemap for either Coloured or Dark theme; add 3D buildings. */
function styleBasemap(map: MLMap, theme: MapTheme) {
  const isDark = theme === "dark";
  const style = map.getStyle();
  for (const l of style.layers ?? []) {
    const id = l.id.toLowerCase();
    if (id.startsWith("tmbg-") || ["area-line", "bus-line", ...TRAFFIC_LAYERS, "glow-casing", "links-flow", "links-selected", "hl-ghost", "hl-casing", "hl-line", "links-hit", "gates-bar"].includes(l.id)) {
      continue;
    }
    try {
      if (l.type === "fill") {
        if (id.includes("building")) {
          map.setPaintProperty(l.id, "fill-color", isDark ? "#1e293b" : "#e2d9c8");
          map.setPaintProperty(l.id, "fill-opacity", isDark ? 0.45 : 0.38);
        } else if (id.includes("water")) {
          map.setPaintProperty(l.id, "fill-color", isDark ? "#0f2942" : "#93c5fd");
        } else if (id.includes("park") || id.includes("wood") || id.includes("grass") || id.includes("landcover")) {
          map.setPaintProperty(l.id, "fill-color", isDark ? "#0f241d" : "#bbf7d0");
        } else if (id.includes("landuse")) {
          map.setPaintProperty(l.id, "fill-color", isDark ? "#111827" : "#ede9fe");
        }
      } else if (l.type === "line" && /road|highway|street|bridge|tunnel/.test(id)) {
        if (id.includes("casing")) {
          map.setPaintProperty(l.id, "line-color", isDark ? "#0f172a" : "#cbd5e1");
        } else if (/motorway|trunk|primary/.test(id)) {
          map.setPaintProperty(l.id, "line-color", isDark ? "#263449" : "#fde68a");
        } else {
          map.setPaintProperty(l.id, "line-color", isDark ? "#1e293b" : "#ffffff");
        }
      } else if (l.type === "symbol") {
        if (id.includes("poi") || id.includes("housenumber")) {
          map.setLayoutProperty(l.id, "visibility", "none");
        } else {
          map.setPaintProperty(l.id, "text-color", isDark ? "#94a3b8" : "#475569");
          map.setPaintProperty(l.id, "text-halo-color", isDark ? "#0f172a" : "#ffffff");
        }
      } else if (l.type === "background") {
        map.setPaintProperty(l.id, "background-color", isDark ? "#0b1120" : "#f4f1ea");
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
          "fill-extrusion-color": isDark ? "#1e293b" : "#d6d3d1",
          "fill-extrusion-height": ["coalesce", ["get", "render_height"], 10],
          "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
          "fill-extrusion-opacity": isDark ? 0.72 : 0.6,
        },
      } as unknown as LayerSpec);
    } catch {
      /* style has no building source-layer */
    }
  } else if (map.getLayer("tmbg-buildings-3d")) {
    try {
      map.setPaintProperty("tmbg-buildings-3d", "fill-extrusion-color", isDark ? "#1e293b" : "#d6d3d1");
      map.setPaintProperty("tmbg-buildings-3d", "fill-extrusion-opacity", isDark ? 0.72 : 0.6);
    } catch {
      /* ignore */
    }
  }
  for (const casing of ["links-casing-a", "links-casing-b"]) {
    if (!map.getLayer(casing)) continue;
    try {
      map.setPaintProperty(casing, "line-color", isDark ? "#0f172a" : "#ffffff");
    } catch {
      /* ignore */
    }
  }
  if (map.getLayer("tmbg-city-mask")) {
    try {
      map.setPaintProperty("tmbg-city-mask", "fill-color", isDark ? "#020617" : "#334155");
      map.setPaintProperty("tmbg-city-mask", "fill-opacity", isDark ? 0.58 : 0.36);
    } catch {
      /* ignore */
    }
  }
}

export default function CorridorMap(props: Props) {
  const {
    data, baseline, baselineJunctions, result, scanRows, layers, mapTheme, showDelta, selectedLinkIds, pins,
    highlight, camera, viewPadding, highlightBus, onPickLink, onPickNothing,
  } = props;
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement | null>(null);
  const [map, setMap] = useState<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const pickRef = useRef(onPickLink);
  pickRef.current = onPickLink;
  const nothingRef = useRef(onPickNothing);
  nothingRef.current = onPickNothing;
  const tRef = useRef(t);
  tRef.current = t;
  const themeRef = useRef(mapTheme);
  themeRef.current = mapTheme;
  const padRef = useRef(viewPadding);
  padRef.current = viewPadding;
  const tiltRef = useRef(layers.buildings3d);
  tiltRef.current = layers.buildings3d;
  /** set when the user drags/zooms the map; stops panel open/close from pulling the view back */
  const userMoved = useRef(false);
  const popup = useRef<maplibregl.Popup | null>(null);
  const pinMarkers = useRef(new Map<string, PinEntry>());
  const hlMarkers = useRef<maplibregl.Marker[]>([]);
  const junctionMarkers = useRef(new Map<string, JunctionEntry>());

  // ---------------------------------------------------------------- init
  useEffect(() => {
    if (!ref.current) return;
    const [s, w, n, e] = data.corridor.bbox;
    const m = new maplibregl.Map({
      container: ref.current,
      style: STYLE_URL,
      center: [(w + e) / 2, (s + n) / 2],
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
    // only real input events carry originalEvent; camera moves started by the app do not
    m.on("movestart", (ev) => {
      if ((ev as { originalEvent?: Event }).originalEvent) userMoved.current = true;
    });
    let framed = false;
    m.on("style.load", () => {
      styleBasemap(m, themeRef.current);
      setup(m);
      styleBasemap(m, themeRef.current);
      if (!framed) {
        framed = true;
        // intro: start a little further out, flat, and glide into the tilted corridor view
        const narrow = window.innerWidth < 768;
        const cam = m.cameraForBounds([[w, s], [e, n]], { padding: narrow ? 30 : { top: 80, bottom: 70, left: 70, right: 70 } });
        if (cam?.center && cam.zoom !== undefined) {
          const tilt = tiltRef.current;
          m.jumpTo({ center: cam.center, zoom: cam.zoom - 1.4, pitch: 0, bearing: 0 });
          m.easeTo({ center: cam.center, zoom: cam.zoom, pitch: tilt ? 42 : 0, bearing: tilt ? -12 : 0, duration: 1800, easing: easeOutCubic });
        }
      }
      setReady(true);
    });
    setMap(m);
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setup(m: MLMap) {
    if (!m.getSource("city-mask")) m.addSource("city-mask", { type: "geojson", data: gj(TIMISOARA_MASK_GEOJSON) });
    if (!m.getSource("city-border")) m.addSource("city-border", { type: "geojson", data: gj(TIMISOARA_BORDER_GEOJSON) });
    for (const id of ["area", "links", "links-a", "links-b", "glow", "bus", "gates", "highlight"]) {
      if (!m.getSource(id)) m.addSource(id, { type: "geojson", data: gj(EMPTY) });
    }
    if (!m.hasImage(GATE_ICON)) m.addImage(GATE_ICON, makeGateIcon(), { pixelRatio: 2 });
    const add = (spec: Record<string, unknown>) => {
      if (!m.getLayer(spec.id as string)) m.addLayer(spec as unknown as LayerSpec);
    };
    const isDark = themeRef.current === "dark";
    add({
      id: "tmbg-city-mask",
      type: "fill",
      source: "city-mask",
      paint: {
        "fill-color": isDark ? "#020617" : "#334155",
        "fill-opacity": isDark ? 0.58 : 0.36,
      },
    });
    add({
      id: "tmbg-city-border",
      type: "line",
      source: "city-border",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#005BBC",
        "line-width": ["interpolate", ["linear"], ["zoom"], 10, 2, 14, 2.5, 17, 3.2],
      },
    });
    const offset = ["interpolate", ["linear"], ["zoom"], 14, 2, 18, 7];
    add({ id: "area-line", type: "line", source: "area", paint: { "line-color": "#94a3b8", "line-width": 1.2, "line-dasharray": [3, 2] } });
    add({ id: "bus-line", type: "line", source: "bus", layout: { "line-cap": "round" },
      paint: { "line-color": ["get", "color"], "line-width": 14, "line-opacity": 0.35, "line-offset": offset } });
    // traffic colours are drawn twice (a below b) so a change can cross-fade instead of snapping
    for (const k of ["a", "b"]) {
      add({ id: `links-casing-${k}`, type: "line", source: `links-${k}`, layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": isDark ? "#0f172a" : "#ffffff", "line-width": ["+", 3, ["get", "w"]], "line-offset": offset,
          "line-opacity": k === "a" ? 1 : 0 } });
      add({ id: `links-line-${k}`, type: "line", source: `links-${k}`, layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": ["get", "w"], "line-offset": offset, "line-opacity": k === "a" ? 1 : 0 } });
    }
    // Braess streets: thin magenta outline, no glow (no-cost streets are only listed in the scan panel)
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
    add({ id: "gates-bar", type: "symbol", source: "gates",
      layout: { "icon-image": GATE_ICON, "icon-rotate": ["get", "rot"], "icon-rotation-alignment": "map", "icon-pitch-alignment": "map",
        "icon-size": ["interpolate", ["linear"], ["zoom"], 13, 0.45, 16, 0.8, 18, 1.1], "icon-allow-overlap": true, "icon-ignore-placement": true } });

    m.on("click", "links-hit", (ev: MapLayerMouseEvent) => {
      const id = ev.features?.[0]?.properties?.id;
      if (id) pickRef.current(String(id));
    });
    // clicking empty map (no street under the cursor) clears the selection; a drag never fires "click"
    m.on("click", (ev) => {
      if (!m.getLayer("links-hit")) return;
      if (m.queryRenderedFeatures(ev.point, { layers: ["links-hit"] }).length === 0) nothingRef.current();
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
          ? `<div class="mt-1 font-secondary text-[11px] text-slate-700">${fmt(Number(p.flow), 0)} ${tt.vehH} · ${fmt(Number(p.timeSec), 0)} ${tt.s}` +
            (Math.abs(d) >= 1 ? `<br/>Δ ${signed(d, 0)} ${tt.vehH}` : "") + `</div>`
          : "") +
        `</div>`;
      if (!popup.current) popup.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: "280px" });
      popup.current.setLngLat(ev.lngLat).setHTML(html);
      // re-adding an open popup rebuilds it (and would replay its fade-in on every mouse move)
      if (!popup.current.isOpen()) popup.current.addTo(m);
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
    (map.getSource("gates") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.gates.features.map((g) => ({
        ...g,
        properties: { ...g.properties, rot: gateRotation(data, g.geometry.coordinates, g.properties.street) },
      })),
    }));
  }, [map, ready, data]);

  // traffic colours: the new state is written to the hidden copy, which fades in while the old one fades out
  // (the old one waits half the time, so the lines never look washed out in between)
  const front = useRef<"a" | "b">("a");
  const linksShown = useRef(false);
  useEffect(() => {
    if (!map || !ready) return;
    (map.getSource("links") as GeoJSONSource).setData(gj(linksFC));
    if (!linksShown.current) {
      linksShown.current = true;
      (map.getSource("links-a") as GeoJSONSource).setData(gj(linksFC));
      fadeInLayers(map, { "links-casing-a": 1, "links-line-a": 1 }, 700);
      return;
    }
    const outgoing = front.current;
    const incoming = outgoing === "a" ? "b" : "a";
    front.current = incoming;
    (map.getSource(`links-${incoming}`) as GeoJSONSource).setData(gj(linksFC));
    const fade = (k: string, opacity: number, delay: number) => {
      for (const id of [`links-casing-${k}`, `links-line-${k}`]) {
        map.setPaintProperty(id, "line-opacity-transition", { duration: CROSSFADE_MS / 2, delay });
        map.setPaintProperty(id, "line-opacity", opacity);
      }
    };
    fade(incoming, 1, 0);
    fade(outgoing, 0, CROSSFADE_MS / 2);
  }, [map, ready, linksFC]);

  // Braess outlines fade in when the search results arrive
  useEffect(() => {
    if (!map || !ready) return;
    (map.getSource("glow") as GeoJSONSource).setData(gj(glowFC));
    fadeInLayers(map, { "glow-casing": 1 }, 600);
  }, [map, ready, glowFC]);

  // the blue band under a newly selected street fades in
  const selectedKey = selectedLinkIds.join(",");
  useEffect(() => {
    if (!map || !ready || !selectedKey) return;
    fadeInLayers(map, { "links-selected": 0.3 }, 400);
  }, [map, ready, selectedKey]);

  useEffect(() => {
    if (!map || !ready) return;
    const ids = new Set(highlightBus?.linkIds ?? []);
    (map.getSource("bus") as GeoJSONSource).setData(gj({
      type: "FeatureCollection",
      features: data.links.features.filter((f) => ids.has(f.properties.id))
        .map((f) => ({ ...f, properties: { color: highlightBus?.color ?? "#7c3aed" } })),
    }));
  }, [map, ready, data, highlightBus]);

  // ---------------------------------------------------------------- basemap theme + layer visibility
  useEffect(() => {
    if (!map || !ready) return;
    styleBasemap(map, mapTheme);
  }, [map, ready, mapTheme]);

  const prev3d = useRef(layers.buildings3d);
  useEffect(() => {
    if (!map || !ready) return;
    const vis = (ids: string[], on: boolean) =>
      ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    vis(TRAFFIC_LAYERS, layers.traffic);
    vis(["links-flow"], layers.traffic && layers.flow);
    vis(["glow-casing"], layers.glow);
    vis(["gates-bar"], layers.gates);
    vis(["tmbg-buildings-3d"], layers.buildings3d);
    if (prev3d.current !== layers.buildings3d) {
      prev3d.current = layers.buildings3d;
      map.easeTo({
        pitch: layers.buildings3d ? 42 : 0,
        bearing: layers.buildings3d ? -12 : 0,
        duration: 700,
        easing: easeOutCubic,
      });
    }
  }, [map, ready, layers]);

  // ---------------------------------------------------------------- intersection markers
  // markers are updated in place (so they do not re-animate on every result); new ones grow in, old ones shrink out
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
          el.className = "queue-pillar";
          const core = document.createElement("span");
          core.className = "queue-core";
          el.appendChild(core);
          entry = { el, core, state: "", marker: new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat(f.geometry.coordinates).addTo(map) };
          store.set(p.id, entry);
        } else if (entry.leaving) {
          window.clearTimeout(entry.leaving);
          entry.leaving = undefined;
          entry.el.classList.remove("queue-leaving");
        }
        const relieved = r && now < was - 3;
        const worse = r && now > was + 3;
        // the base red-light wait (~14 s at a 90 s cycle) is normal; queueing on top of it turns the marker yellow, red, then dark red
        const state = now >= 60 ? "jammed" : now >= 35 ? "saturated" : now >= 20 ? "busy" : "free";
        const classes = [`queue-${relieved ? "resolved" : state}`, ...(worse ? ["queue-worse"] : [])];
        const key = classes.join(" ");
        if (entry.state !== key) {
          // classList keeps the classes MapLibre puts on the marker element
          entry.el.classList.remove(...entry.state.split(" ").filter(Boolean));
          entry.el.classList.add(...classes);
          entry.state = key;
        }
        entry.el.style.setProperty("--qsize", `${Math.min(44, 16 + now / 2)}px`);
        entry.el.title = `${p.name}\n${fmt(was, 0)} s → ${fmt(now, 0)} s`;
        // colour and size carry the wait; the exact seconds are in the tooltip
      }
    }
    store.forEach((entry, id) => {
      if (seen.has(id) || entry.leaving) return;
      entry.el.classList.add("queue-leaving");
      entry.leaving = window.setTimeout(() => {
        entry.marker.remove();
        store.delete(id);
      }, 220);
    });
  }, [map, ready, data, baselineJunctions, result, layers.intersections]);

  useEffect(() => {
    const store = junctionMarkers.current;
    const pinsStore = pinMarkers.current;
    return () => {
      store.forEach((e) => {
        window.clearTimeout(e.leaving);
        e.marker.remove();
      });
      store.clear();
      pinsStore.forEach((e) => {
        window.clearTimeout(e.leaving);
        e.marker.remove();
      });
      pinsStore.clear();
    };
  }, []);

  // ---------------------------------------------------------------- travel-time pins
  // kept by street: a new pin drops in, a removed one fades out, a changed time flashes briefly
  useEffect(() => {
    if (!map || !ready) return;
    const store = pinMarkers.current;
    const seen = new Set<string>();
    for (const p of pins) {
      seen.add(p.key);
      const changed = p.beforeSec !== null && p.afterSec !== null && Math.abs(p.afterSec - p.beforeSec) >= 0.5;
      const faster = changed && (p.afterSec as number) < (p.beforeSec as number);
      const timeHtml = `${p.beforeSec === null ? "—" : fmt(p.beforeSec / 60, 2)}` +
        (changed ? ` → <b>${fmt((p.afterSec as number) / 60, 2)}</b>` : "") + ` min`;
      let entry = store.get(p.key);
      if (!entry) {
        const el = document.createElement("div");
        el.className = "tmbg-pin";
        const card = document.createElement("div");
        const title = document.createElement("div");
        title.className = "tmbg-pin-title";
        const time = document.createElement("div");
        time.className = "tmbg-pin-time";
        const stem = document.createElement("div");
        stem.className = "tmbg-pin-stem";
        card.append(title, time);
        el.append(card, stem);
        entry = { el, card, title, time, timeHtml: "", marker: new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(p.at).addTo(map) };
        store.set(p.key, entry);
      } else {
        if (entry.leaving) {
          window.clearTimeout(entry.leaving);
          entry.leaving = undefined;
          entry.el.classList.remove("is-leaving");
        }
        entry.marker.setLngLat(p.at);
      }
      entry.card.className = `tmbg-pin-card ${changed ? (faster ? "tmbg-pin-faster" : "tmbg-pin-slower") : ""}`;
      entry.title.textContent = p.label;
      if (entry.timeHtml !== timeHtml) {
        const first = entry.timeHtml === "";
        entry.time.innerHTML = timeHtml;
        entry.timeHtml = timeHtml;
        if (!first) animateEl(entry.time, [{ backgroundColor: "rgba(250, 204, 21, 0.55)" }, { backgroundColor: "rgba(250, 204, 21, 0)" }], { duration: 900, easing: "ease-out" });
      }
    }
    store.forEach((entry, key) => {
      if (seen.has(key) || entry.leaving) return;
      entry.el.classList.add("is-leaving");
      entry.leaving = window.setTimeout(() => {
        entry.marker.remove();
        store.delete(key);
      }, 200);
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
      const mk = (html: string, at: LngLat, anchor: maplibregl.PositionAnchor = "center") => {
        // the marker element only holds position; its child carries the look and the entrance animation
        const el = document.createElement("div");
        el.className = "tmbg-hl";
        el.innerHTML = html;
        hlMarkers.current.push(new maplibregl.Marker({ element: el, anchor }).setLngLat(at).addTo(map));
      };
      const c = highlight.coordinates;
      mk(`<div class="route-pin route-pin-start">A</div>`, c[0]);
      mk(`<div class="route-pin route-pin-end">B</div>`, c[c.length - 1]);
      mk(`<div class="route-callout">${highlight.label} · <b>${highlight.time}</b></div>`,
        c[Math.floor(c.length / 2)], "bottom");
    }
    (map.getSource("highlight") as GeoJSONSource).setData(gj({ type: "FeatureCollection", features: feats }));
    if (feats.length) fadeInLayers(map, { "hl-casing": 1, "hl-line": 1, "hl-ghost": 0.8 }, 300);
  }, [map, ready, highlight]);

  // ---------------------------------------------------------------- camera
  // A new target flies there (zooming out and back in on long jumps). When a panel opens or closes, the current
  // target is eased back into the middle of the free space, unless the user has moved the map in the meantime.
  const target = useRef<CameraTarget | null>(null);
  const lastCameraKey = useRef(0);
  const refitTimer = useRef(0);
  const padKey = `${viewPadding.top},${viewPadding.right},${viewPadding.bottom},${viewPadding.left}`;
  useEffect(() => {
    if (!map || !ready) return;
    const go = (tgt: CameraTarget, fly: boolean) => {
      if (tgt.coords.length === 0) return;
      const pad = padRef.current;
      const b = new maplibregl.LngLatBounds();
      tgt.coords.forEach((ll) => b.extend(ll as [number, number]));
      const cam = map.cameraForBounds(b, { padding: pad, maxZoom: 17, bearing: map.getBearing() });
      if (!cam?.center || cam.zoom === undefined) return;
      if (fly) map.flyTo({ center: cam.center, zoom: cam.zoom, bearing: map.getBearing(), pitch: map.getPitch(), speed: 1.3, curve: 1.42, maxDuration: 1600 });
      else map.easeTo({ center: cam.center, zoom: cam.zoom, duration: 500, easing: easeOutCubic });
    };
    window.clearTimeout(refitTimer.current);
    if (camera && camera.key !== lastCameraKey.current) {
      lastCameraKey.current = camera.key;
      target.current = camera;
      userMoved.current = false;
      if (camera.mode === "ensure" && comfortablyVisible(map, camera.coords, padRef.current)) return;
      go(camera, true);
      return;
    }
    // panels opened/closed: wait a moment, a selection that opened the panel brings its own (newer) target
    refitTimer.current = window.setTimeout(() => {
      if (target.current && !userMoved.current) go(target.current, false);
    }, 60);
    return () => window.clearTimeout(refitTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, ready, camera?.key, padKey]);

  // ---------------------------------------------------------------- animation: flow dashes
  useEffect(() => {
    if (!map || !ready) return;
    let raf = 0;
    let last = 0;
    const tick = (ts: number) => {
      if (ts - last > 55) {
        last = ts;
        if (map.getLayer("links-flow")) map.setPaintProperty("links-flow", "line-dasharray", DASHES[Math.floor(ts / 55) % DASHES.length]);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [map, ready]);

  return (
    <div className="absolute inset-0">
      <div ref={ref} className="h-full w-full" />
    </div>
  );
}
