import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, StyleSpecification } from "maplibre-gl";
import type {
  ColorMode,
  HighlightedRoute,
  LayerState,
  LngLat,
  NetworkResponse,
  RoadProps,
  SimulateResponse,
} from "../../types/simulator";
import { useI18n } from "../../i18n/translations";
import { fmt, signed } from "../../lib/format";
import IntersectionQueueMarkers from "./IntersectionQueueMarkers";

type GJ = Parameters<GeoJSONSource["setData"]>[0];
type LayerSpec = Parameters<MLMap["addLayer"]>[0];
const gj = (x: unknown) => x as GJ;
const layer = (x: unknown) => x as LayerSpec;

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const CENTER: LngLat = [21.2285, 45.7537];
const FONT = ["Noto Sans Regular"];

const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#f1f5f9" } }],
};

// Animated dash sequence (MapLibre "animate a line" technique)
const DASH_SEQ: number[][] = [
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
];

export interface FlyTarget {
  center: LngLat;
  zoom: number;
  key: number;
}

interface Props {
  network: NetworkResponse | null;
  sim: SimulateResponse | null;
  layers: LayerState;
  colorMode: ColorMode;
  selectedLinkId: string | null;
  editedLinkIds: string[];
  highlighted: HighlightedRoute | null;
  focusKey: number;
  flyTo: FlyTarget | null;
  onSelectLink: (id: string) => void;
}

/** Mute the positron basemap so the simulated network has maximum contrast (§9.1). */
function muteBasemap(map: MLMap) {
  const style = map.getStyle();
  for (const l of style.layers ?? []) {
    const id = l.id.toLowerCase();
    try {
      if (l.type === "fill") {
        if (id.includes("building")) {
          map.setPaintProperty(l.id, "fill-color", "#e2e8f0");
          map.setPaintProperty(l.id, "fill-opacity", 0.45);
        } else if (id.includes("water")) {
          map.setPaintProperty(l.id, "fill-color", "#dbe4ee");
        } else if (id.includes("park") || id.includes("landuse") || id.includes("landcover") || id.includes("wood")) {
          map.setPaintProperty(l.id, "fill-color", "#eef2f6");
        }
      } else if (l.type === "line" && (id.includes("road") || id.includes("highway") || id.includes("street") ||
        id.includes("bridge") || id.includes("tunnel"))) {
        map.setPaintProperty(l.id, "line-color", id.includes("casing") ? "#cbd5e1" : "#ffffff");
      } else if (l.type === "symbol") {
        if (id.includes("poi") || id.includes("housenumber")) {
          map.setLayoutProperty(l.id, "visibility", "none");
        } else {
          map.setPaintProperty(l.id, "text-color", "#94a3b8");
        }
      } else if (l.type === "background") {
        map.setPaintProperty(l.id, "background-color", "#f1f5f9");
      }
    } catch {
      /* layer lacks that paint property */
    }
  }
}

function emptyFC() {
  return { type: "FeatureCollection", features: [] };
}

export default function TrafficMapCanvas(props: Props) {
  const { network, sim, layers, colorMode, selectedLinkId, editedLinkIds, highlighted, focusKey, flyTo, onSelectLink } =
    props;
  const { t, lang } = useI18n();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [map, setMap] = useState<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const pinsRef = useRef<maplibregl.Marker[]>([]);
  const onSelectRef = useRef(onSelectLink);
  onSelectRef.current = onSelectLink;
  const tRef = useRef(t);
  tRef.current = t;

  // ---------------------------------------------------------------- init
  useEffect(() => {
    if (!containerRef.current) return;
    const m = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: CENTER,
      zoom: 13.6,
      pitch: 35,
      bearing: -8,
      attributionControl: false,
      maxZoom: 18.5,
      minZoom: 11,
    });
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    m.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: "© OpenStreetMap contributors · OpenFreeMap · PMT/SMTT",
      }),
      "bottom-right",
    );
    let fellBack = false;
    m.on("error", (e) => {
      // Tiles unreachable (offline demo) → keep the simulator usable on a plain background.
      if (!fellBack && !m.isStyleLoaded() && String(e.error?.message ?? "").toLowerCase().includes("fetch")) {
        fellBack = true;
        m.setStyle(FALLBACK_STYLE);
      }
    });
    m.on("style.load", () => {
      muteBasemap(m);
      setReady(false);
      addSimLayers(m);
      setReady(true);
    });
    mapRef.current = m;
    setMap(m);
    return () => {
      m.remove();
      mapRef.current = null;
    };
  }, []);

  function addSimLayers(m: MLMap) {
    const src = (id: string, promoteId?: string) => {
      if (!m.getSource(id)) {
        m.addSource(id, { type: "geojson", data: gj(emptyFC()), ...(promoteId ? { promoteId } : {}) });
      }
    };
    ["zones", "timpark", "stpt", "cycleways", "ivelo", "pois", "events", "sesizari", "air", "routes", "highlight"].forEach(
      (s) => src(s),
    );
    src("roads", "id");

    const add = (spec: Record<string, unknown>) => {
      if (!m.getLayer(spec.id as string)) m.addLayer(layer(spec));
    };
    // --- context layers (bottom)
    add({ id: "zones-fill", type: "fill", source: "zones", paint: { "fill-color": "#64748b", "fill-opacity": 0.04 } });
    add({ id: "zones-line", type: "line", source: "zones", paint: { "line-color": "#94a3b8", "line-width": 1, "line-dasharray": [2, 2] } });
    add({
      id: "zones-label", type: "symbol", source: "zones",
      layout: { "text-field": ["get", "name"], "text-font": FONT, "text-size": 11, "text-letter-spacing": 0.05 },
      paint: { "text-color": "#64748b", "text-halo-color": "#f8fafc", "text-halo-width": 1.5 },
    });
    add({
      id: "timpark-fill", type: "fill", source: "timpark", filter: ["==", ["geometry-type"], "Polygon"],
      paint: {
        "fill-color": ["match", ["get", "zone"], "green", "#16a34a", "red", "#dc2626", "yellow", "#eab308", "blue", "#2563eb", "#94a3b8"],
        "fill-opacity": 0.1,
      },
    });
    add({
      id: "timpark-line", type: "line", source: "timpark",
      paint: {
        "line-color": ["match", ["get", "zone"], "green", "#16a34a", "red", "#dc2626", "yellow", "#eab308", "blue", "#2563eb", "#94a3b8"],
        "line-width": 1.5, "line-opacity": 0.7,
      },
    });
    add({
      id: "stpt-line", type: "line", source: "stpt",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["coalesce", ["get", "color"], "#7c3aed"], "line-width": 2.2, "line-opacity": 0.55 },
    });
    add({
      id: "stpt-label", type: "symbol", source: "stpt",
      layout: { "symbol-placement": "line", "text-field": ["get", "shortName"], "text-font": FONT, "text-size": 10, "symbol-spacing": 220 },
      paint: { "text-color": "#334155", "text-halo-color": "#ffffff", "text-halo-width": 2 },
    });
    add({
      id: "cycleways-line", type: "line", source: "cycleways",
      layout: { "line-cap": "round" },
      paint: { "line-color": "#059669", "line-width": 2.4, "line-dasharray": [1, 1.2], "line-opacity": 0.85 },
    });

    // --- simulated road network
    add({
      id: "roads-halo", type: "line", source: "roads", filter: ["==", ["get", "isBraessCandidate"], true],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#10b981", "line-width": ["interpolate", ["linear"], ["zoom"], 12, 9, 16, 22], "line-blur": 6, "line-opacity": 0.45, "line-offset": 3 },
    });
    add({
      id: "roads-casing", type: "line", source: "roads",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#ffffff",
        "line-width": ["interpolate", ["linear"], ["zoom"], 12, ["+", 1.5, ["*", 0.0025, ["get", "flow"]]], 16, ["+", 5, ["*", 0.007, ["get", "flow"]]]],
        "line-offset": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 5],
      },
    });
    add({
      id: "roads-line", type: "line", source: "roads",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#94a3b8",
        "line-width": ["interpolate", ["linear"], ["zoom"], 12, ["+", 1, ["*", 0.002, ["get", "flow"]]], 16, ["+", 3, ["*", 0.006, ["get", "flow"]]]],
        "line-offset": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 5],
      },
    });
    add({
      id: "roads-braess-casing", type: "line", source: "roads", filter: ["==", ["get", "isBraessCandidate"], true],
      paint: { "line-color": "#d946ef", "line-width": 1.2, "line-gap-width": ["interpolate", ["linear"], ["zoom"], 12, 3, 16, 9], "line-offset": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 5], "line-opacity": 0.85 },
    });
    add({
      id: "roads-flow", type: "line", source: "roads", filter: [">", ["get", "flow"], 120],
      layout: { "line-cap": "butt" },
      paint: {
        "line-color": "rgba(255,255,255,0.85)",
        "line-width": ["interpolate", ["linear"], ["zoom"], 12, 1, 16, 2.4],
        "line-offset": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 5],
        "line-dasharray": DASH_SEQ[0],
      },
    });
    add({
      id: "roads-edited", type: "line", source: "roads", filter: ["in", ["get", "id"], ["literal", []]],
      paint: { "line-color": "#059669", "line-width": ["interpolate", ["linear"], ["zoom"], 12, 3, 16, 8], "line-offset": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 5], "line-dasharray": [0.6, 0.6] },
    });
    add({
      id: "roads-selected", type: "line", source: "roads", filter: ["==", ["get", "id"], ""],
      layout: { "line-cap": "round" },
      paint: { "line-color": "#005BBC", "line-width": ["interpolate", ["linear"], ["zoom"], 12, 5, 16, 14], "line-opacity": 0.35, "line-offset": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 5] },
    });
    add({
      id: "roads-hit", type: "line", source: "roads",
      paint: { "line-color": "#000000", "line-opacity": 0, "line-width": 14, "line-offset": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 5] },
    });

    // --- recommended routes
    add({
      id: "routes-car", type: "line", source: "routes", filter: ["==", ["get", "kind"], "car_arterial"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#2563eb", "line-width": 3, "line-opacity": 0.45, "line-offset": -4 },
    });
    add({
      id: "routes-cut", type: "line", source: "routes", filter: ["==", ["get", "kind"], "car_cut_through"],
      paint: { "line-color": "#dc2626", "line-width": 3, "line-opacity": 0.75, "line-dasharray": [1.5, 1.2], "line-offset": -4 },
    });
    add({
      id: "highlight-casing", type: "line", source: "highlight",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#ffffff", "line-width": 11, "line-opacity": 0.95 },
    });
    add({
      id: "highlight-line", type: "line", source: "highlight",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ["get", "color"], "line-width": 6 },
    });
    add({
      id: "highlight-dash", type: "line", source: "highlight", filter: ["==", ["get", "kind"], "car_cut_through"],
      paint: { "line-color": "#ffffff", "line-width": 2.5, "line-dasharray": [1, 1.5] },
    });

    // --- points
    add({ id: "ivelo-circle", type: "circle", source: "ivelo", paint: { "circle-radius": 4.5, "circle-color": "#059669", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } });
    add({ id: "pois-circle", type: "circle", source: "pois", paint: { "circle-radius": 4.5, "circle-color": "#005BBC", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } });
    add({
      id: "pois-label", type: "symbol", source: "pois", minzoom: 14.5,
      layout: { "text-field": ["get", "name"], "text-font": FONT, "text-size": 10.5, "text-offset": [0, 1.1], "text-anchor": "top", "text-max-width": 9 },
      paint: { "text-color": "#1e3a8a", "text-halo-color": "#ffffff", "text-halo-width": 1.5 },
    });
    add({ id: "events-circle", type: "circle", source: "events", paint: { "circle-radius": 5, "circle-color": "#d946ef", "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 } });
    add({
      id: "sesizari-circle", type: "circle", source: "sesizari",
      paint: { "circle-radius": ["interpolate", ["linear"], ["get", "total"], 0, 8, 20, 22], "circle-color": "#D97706", "circle-opacity": 0.22, "circle-stroke-color": "#D97706", "circle-stroke-width": 1.5 },
    });
    add({
      id: "sesizari-label", type: "symbol", source: "sesizari",
      layout: { "text-field": ["to-string", ["get", "total"]], "text-font": FONT, "text-size": 12 },
      paint: { "text-color": "#92400e" },
    });
    add({
      id: "air-circle", type: "circle", source: "air",
      paint: { "circle-radius": 9, "circle-color": ["case", [">", ["get", "pm10"], 30], "#f59e0b", "#10b981"], "circle-opacity": 0.85, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 },
    });
    add({
      id: "air-label", type: "symbol", source: "air",
      layout: { "text-field": ["concat", "PM10 ", ["to-string", ["get", "pm10"]]], "text-font": FONT, "text-size": 10, "text-offset": [0, 1.5], "text-anchor": "top" },
      paint: { "text-color": "#334155", "text-halo-color": "#ffffff", "text-halo-width": 1.5 },
    });

    // --- interaction
    m.on("click", "roads-hit", (e: MapLayerMouseEvent) => {
      const f = e.features?.[0];
      if (f?.properties?.id) onSelectRef.current(String(f.properties.id));
    });
    m.on("mouseenter", "roads-hit", () => (m.getCanvas().style.cursor = "pointer"));
    m.on("mouseleave", "roads-hit", () => {
      m.getCanvas().style.cursor = "";
      popupRef.current?.remove();
    });
    m.on("mousemove", "roads-hit", (e: MapLayerMouseEvent) => {
      const p = e.features?.[0]?.properties as Record<string, unknown> | undefined;
      if (!p) return;
      const tt = tRef.current;
      const v = p.braessValueV as number | null | undefined;
      const html =
        `<div class="text-[12px] leading-snug"><div class="font-semibold text-slate-900">${String(p.streetName)}</div>` +
        `<div class="text-slate-500">${String(p.fromName)} → ${String(p.toName)}</div>` +
        `<div class="mt-1 font-mono text-[11px] text-slate-700">${tt.flow}: ${fmt(Number(p.flow), 0)} veh/h · v/c ${fmt(Number(p.vOverC), 2)}` +
        (typeof v === "number" ? `<br/>${tt.prescanV}: <span class="${v < 0 ? "text-emerald-700" : "text-slate-700"}">V = ${signed(v)} ${tt.vehMin}</span>` : "") +
        (p.deltaFlow !== undefined && Math.abs(Number(p.deltaFlow)) > 0.5 ? `<br/>Δ ${signed(Number(p.deltaFlow), 0)} veh/h` : "") +
        `</div></div>`;
      if (!popupRef.current) {
        popupRef.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12, maxWidth: "280px" });
      }
      popupRef.current.setLngLat(e.lngLat).setHTML(html).addTo(m);
    });
  }

  // ---------------------------------------------------------------- data: roads merged with simulation
  const roadsFC = useMemo(() => {
    if (!network) return null;
    const upd = new Map((sim?.updatedLinks ?? []).map((u) => [u.id, u]));
    return {
      type: "FeatureCollection",
      features: network.roads.features.map((f) => {
        const p: RoadProps = f.properties;
        const u = upd.get(p.id);
        const flow = u ? u.flow : p.baselineFlow;
        const tt = u ? u.travelTimeSec : p.travelTimeSec;
        const ff = (p.lengthM / 1000 / p.freeFlowSpeedKmh) * 3600;
        return {
          type: "Feature",
          id: f.id,
          geometry: f.geometry,
          properties: {
            ...p,
            flow,
            vOverC: u ? u.vOverC : p.vOverC,
            speedKmh: u ? u.speedKmh : p.speedKmh,
            deltaFlow: u ? u.deltaFlow : 0,
            slowness: ff > 0 ? tt / ff : 1,
          },
        };
      }),
    };
  }, [network, sim]);

  useEffect(() => {
    if (!map || !ready || !roadsFC) return;
    (map.getSource("roads") as GeoJSONSource | undefined)?.setData(gj(roadsFC));
  }, [map, ready, roadsFC]);

  useEffect(() => {
    if (!map || !ready || !network) return;
    const set = (id: string, data: unknown) => (map.getSource(id) as GeoJSONSource | undefined)?.setData(gj(data));
    const o = network.overlays;
    set("zones", o.zones);
    set("timpark", o.timparkSegments);
    set("stpt", o.stptLines);
    set("cycleways", o.osmCycleways);
    set("ivelo", o.iveloStations);
    set("pois", o.pois);
    set("events", o.events);
    set("sesizari", o.sesizariClusters);
    set("air", o.airQuality);
  }, [map, ready, network]);

  // ---------------------------------------------------------------- color mode
  useEffect(() => {
    if (!map || !ready) return;
    const absolute = [
      "interpolate", ["linear"], ["get", "slowness"],
      1.0, "#10b981", 1.12, "#3b82f6", 1.35, "#f59e0b", 1.9, "#ef4444",
    ];
    const delta = [
      "interpolate", ["linear"], ["get", "deltaFlow"],
      -400, "#1d4ed8", -60, "#10b981", -5, "#cbd5e1", 5, "#cbd5e1", 60, "#fb923c", 400, "#c2410c",
    ];
    map.setPaintProperty("roads-line", "line-color", colorMode === "delta" && sim ? delta : absolute);
  }, [map, ready, colorMode, sim]);

  // ---------------------------------------------------------------- visibility
  useEffect(() => {
    if (!map || !ready) return;
    const vis = (ids: string[], on: boolean) =>
      ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    vis(["roads-casing", "roads-line"], layers.traffic);
    vis(["roads-halo", "roads-braess-casing"], layers.braess);
    vis(["roads-flow"], layers.flowAnimation && layers.traffic);
    vis(["stpt-line", "stpt-label"], layers.stpt);
    vis(["cycleways-line", "ivelo-circle"], layers.cycling);
    vis(["timpark-fill", "timpark-line"], layers.timpark);
    vis(["zones-fill", "zones-line", "zones-label"], layers.zones);
    vis(["sesizari-circle", "sesizari-label"], layers.sesizari);
    vis(["pois-circle", "pois-label", "events-circle"], layers.pois);
    vis(["air-circle", "air-label"], layers.airQuality);
  }, [map, ready, layers]);

  // ---------------------------------------------------------------- selection / edited
  useEffect(() => {
    if (!map || !ready) return;
    map.setFilter("roads-selected", ["==", ["get", "id"], selectedLinkId ?? ""]);
    map.setFilter("roads-edited", ["in", ["get", "id"], ["literal", editedLinkIds]]);
  }, [map, ready, selectedLinkId, editedLinkIds]);

  // ---------------------------------------------------------------- recommended routes
  useEffect(() => {
    if (!map || !ready) return;
    const feats = (sim?.recommendedRoutes.carRoutes ?? []).map((r) => ({
      type: "Feature",
      geometry: { type: "LineString", coordinates: r.coordinates },
      properties: { id: r.id, kind: r.role === "recommended_arterial" ? "car_arterial" : "car_cut_through" },
    }));
    (map.getSource("routes") as GeoJSONSource | undefined)?.setData(gj({ type: "FeatureCollection", features: feats }));
  }, [map, ready, sim]);

  useEffect(() => {
    if (!map || !ready) return;
    pinsRef.current.forEach((p) => p.remove());
    pinsRef.current = [];
    const data = highlighted
      ? {
          type: "FeatureCollection",
          features: [{ type: "Feature", geometry: { type: "LineString", coordinates: highlighted.coordinates },
            properties: { color: highlighted.color, kind: highlighted.kind } }],
        }
      : emptyFC();
    (map.getSource("highlight") as GeoJSONSource | undefined)?.setData(gj(data));
    if (highlighted && highlighted.coordinates.length >= 2) {
      const mk = (cls: string, html: string, at: LngLat, anchor: maplibregl.PositionAnchor = "center") => {
        const el = document.createElement("div");
        el.className = cls;
        el.innerHTML = html;
        pinsRef.current.push(new maplibregl.Marker({ element: el, anchor }).setLngLat(at).addTo(map));
      };
      const c = highlighted.coordinates;
      mk("route-pin route-pin-start", "A", c[0]);
      mk("route-pin route-pin-end", "B", c[c.length - 1]);
      const mid = c[Math.floor(c.length / 2)];
      mk("route-callout", `<span style="background:${highlighted.color}"></span>${highlighted.label} · <b>${highlighted.timeLabel}</b>`, mid, "bottom");
    }
  }, [map, ready, highlighted]);

  useEffect(() => {
    if (!map || !ready || !highlighted || focusKey === 0) return;
    const b = new maplibregl.LngLatBounds();
    highlighted.coordinates.forEach((c) => b.extend(c));
    map.fitBounds(b, { padding: { top: 120, bottom: 120, left: 420, right: 460 }, maxZoom: 15.5, duration: 900 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusKey]);

  useEffect(() => {
    if (!map || !flyTo) return;
    map.flyTo({ center: flyTo.center, zoom: flyTo.zoom, pitch: 40, duration: 1400, essential: true });
  }, [map, flyTo]);

  // ---------------------------------------------------------------- animation: flow dashes + Braess halo pulse
  useEffect(() => {
    if (!map || !ready) return;
    let raf = 0;
    let step = -1;
    let last = 0;
    const tick = (ts: number) => {
      if (ts - last > 55) {
        last = ts;
        const next = Math.floor(ts / 55) % DASH_SEQ.length;
        if (next !== step && map.getLayer("roads-flow")) {
          step = next;
          map.setPaintProperty("roads-flow", "line-dasharray", DASH_SEQ[step]);
        }
        if (map.getLayer("roads-halo")) {
          map.setPaintProperty("roads-halo", "line-opacity", 0.28 + 0.27 * (0.5 + 0.5 * Math.sin(ts / 420)));
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [map, ready]);

  return (
    <div className="absolute inset-0" aria-label={lang === "ro" ? "Hartă trafic Timișoara" : "Timișoara traffic map"}>
      <div ref={containerRef} className="h-full w-full" />
      {map && ready && network && layers.queues && (
        <IntersectionQueueMarkers map={map} queues={network.queues.features} updates={sim?.updatedQueues ?? null} />
      )}
    </div>
  );
}
