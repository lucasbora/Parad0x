import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, HelpCircle, Leaf, Loader2, Menu, Palette, RefreshCw, Search, Undo2, X } from "lucide-react";
import { api, signed } from "./api";
import { I18nContext, translations, type Lang } from "./i18n/translations";
import type {
  BaselineLink,
  BusResult,
  Change,
  CorridorResponse,
  Highlight,
  LaneKind,
  LaneUse,
  LngLat,
  MapLayers,
  PackageResponse,
  Pin,
  PinSnapshot,
  Profile,
  ScanRow,
  SimulateResponse,
} from "./types/corridor";
import CorridorMap, { type CameraTarget, type MapPinView, type MapTheme, type ViewPadding } from "./components/CorridorMap";
import LayersPill from "./components/LayersPill";
import StreetSearch from "./components/StreetSearch";
import LaneMixer from "./components/LaneMixer";
import PinsPanel, { type PinTime } from "./components/PinsPanel";
import ScanCard from "./components/ScanCard";
import ResultsPanel from "./components/ResultsPanel";
import SourcesNote from "./components/SourcesNote";
import ProfileBar from "./components/ProfileBar";
import CitizenBraessExplainerModal from "./components/CitizenBraessExplainerModal";
import { usePresence, useSlidingThumb, withViewTransition } from "./motion";

function readLang(): Lang {
  try {
    return window.localStorage.getItem("tmbg.lang") === "en" ? "en" : "ro";
  } catch {
    return "ro";
  }
}

const pinKey = (p: Pin) => `${p.street}|${p.heading}`;
const DEFAULT_LAYERS: MapLayers = { traffic: true, glow: true, flow: true, intersections: true, gates: true, buildings3d: true };

function DarkMapIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7 rounded-md" aria-hidden="true">
      <rect width="32" height="32" rx="6" fill="#0b1120" />
      <path d="M0 7h12v10H0z" fill="#0f241d" />
      <path d="M18 18h14v14H18z" fill="#131c31" />
      <path d="M-2 23C6 21 12 15 17 16c6 1 9-5 17-7v8c-7 2-10 8-17 7-5-1-10 4-19 6z" fill="#0f2942" />
      <path d="M11 0v32M0 13h32M22 0v32" stroke="#1e293b" strokeWidth="2.2" />
      <path d="M3 30L29 4" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="5.5" fill="none" stroke="#334155" />
    </svg>
  );
}

function ColoredMapIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-7 w-7 rounded-md" aria-hidden="true">
      <rect width="32" height="32" rx="6" fill="#f4f1ea" />
      <path d="M0 0h13v13H0z" fill="#86efac" />
      <path d="M19 19h13v13H19z" fill="#bbf7d0" />
      <path d="M-2 23C6 21 12 15 17 16c6 1 9-5 17-7v8c-7 2-10 8-17 7-5-1-10 4-19 6z" fill="#60a5fa" />
      <path d="M11 0v32M0 13h32M22 0v32" stroke="#ffffff" strokeWidth="2.4" />
      <path d="M3 30L29 4" stroke="#fbbf24" strokeWidth="2.4" strokeLinecap="round" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="5.5" fill="none" stroke="#cbd5e1" />
    </svg>
  );
}

/** Mixer lanes that reproduce a scan row: −1 lane → last lane becomes a bike lane; a removal is a scenario, lanes untouched. */
function scanLanes(r: ScanRow, original: LaneKind[]): LaneKind[] {
  if (r.kind === "lane") return original.map((l, i) => (i === original.length - 1 ? "bike" : l));
  return original;
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(readLang);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem("tmbg.lang", l);
    } catch {
      /* storage unavailable */
    }
  }, []);
  const i18n = useMemo(() => ({ lang, t: translations[lang], setLang }), [lang, setLang]);
  const t = i18n.t;

  const [data, setData] = useState<CorridorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [profile, setProfile] = useState<Profile>("morning");
  const [demandInput, setDemandInput] = useState(1);        // slider position (moves instantly)
  const [demandScale, setDemandScale] = useState(1);        // applied after a short pause
  const [demandVehH, setDemandVehH] = useState<number | null>(null);
  const [baseline, setBaseline] = useState<BaselineLink[] | null>(null);
  const [baselineJunctions, setBaselineJunctions] = useState<{ nodeId: string; delaySec: number }[] | null>(null);
  const [scanRows, setScanRows] = useState<ScanRow[] | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanStats, setScanStats] = useState<{ tested: number; seconds: number } | null>(null);
  /** A segment from the Braess search closed in BOTH directions (not expressible as lanes of one direction). */
  const [scenario, setScenario] = useState<ScanRow | null>(null);
  const [pkg, setPkg] = useState<PackageResponse | null>(null);
  const [evaporation, setEvaporation] = useState(0);

  const [street, setStreet] = useState<string | null>(null);
  const [heading, setHeading] = useState<string | null>(null);
  const [lanes, setLanes] = useState<LaneKind[]>([]);
  const pendingScan = useRef<ScanRow | null>(null);
  const pendingLanes = useRef<{ street: string; heading: string; lanes: LaneKind[] } | null>(null);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [pins, setPins] = useState<Pin[]>([]);
  const [layers, setLayers] = useState<MapLayers>(DEFAULT_LAYERS);
  const [showDelta, setShowDelta] = useState(false);
  const [hoverBus, setHoverBus] = useState<BusResult | null>(null);
  const [hovered, setHovered] = useState<Highlight | null>(null);
  const [pinned, setPinned] = useState<Highlight | null>(null);
  const [camera, setCamera] = useState<CameraTarget | null>(null);
  const [explainer, setExplainer] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // the layers panel starts open (except on phones, where it would cover the map) and slides down
  // whenever the street panel opens, from the menu or by clicking a street; the user can reopen it any time
  const [layersOpen, setLayersOpen] = useState(() => window.innerWidth >= 768);
  useEffect(() => {
    if (sidebarOpen) setLayersOpen(false);
  }, [sidebarOpen]);
  const [recommendedOpen, setRecommendedOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);
  const [mapTheme, setMapTheme] = useState<MapTheme>("colored");
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menu = usePresence(menuOpen, 150);
  const themeMenu = usePresence(themeMenuOpen, 150);
  const langThumb = useSlidingThumb(lang);

  useEffect(() => {
    if (!menuOpen) {
      setThemeMenuOpen(false);
      return;
    }
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    document.documentElement.classList.toggle("theme-dark", mapTheme === "dark");
  }, [mapTheme]);

  // ------------------------------------------------------------ network + data status
  useEffect(() => {
    setError(null);
    api.corridor()
      .then((d) => {
        setData(d);
        setProfile((p) => (d.profiles.some((x) => x.id === p) ? p : d.defaultProfile));
      })
      .catch((e: Error) => setError(e.message));
  }, [reload]);

  useEffect(() => {
    const id = window.setTimeout(() => setDemandScale(demandInput), 300);
    return () => window.clearTimeout(id);
  }, [demandInput]);

  // current traffic (coloured map + intersection markers), the Braess search and the model check — per time of day.
  // Demand is always available (estimated from OSM land use, calibrated when counts exist).
  useEffect(() => {
    if (!data) return;
    let live = true;
    setScanRows(null);
    setScanStats(null);
    setScanLoading(true);
    setPkg(null);
    api.scan(profile).then((s) => {
      if (!live) return;
      setScanRows(s.status === "ok" ? s.rows : null);
      setScanStats(s.status === "ok" ? { tested: s.tested.removal + s.tested.lane, seconds: s.seconds } : null);
      // the package reuses the cached search, so ask only after it is done
      if (s.status === "ok") api.package(profile).then((p) => live && setPkg(p)).catch(() => undefined);
    }).catch(() => undefined)
      .finally(() => live && setScanLoading(false));
    return () => {
      live = false;
    };
  }, [data, profile]);

  // the coloured map follows both the time of day and the demand level
  useEffect(() => {
    if (!data) return;
    let live = true;
    api.baseline(profile, demandScale).then((b) => {
      if (!live || b.status !== "ok") return;
      setBaseline(b.links);
      setBaselineJunctions(b.junctions);
      setDemandVehH(b.demandVehH);
    }).catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [data, profile, demandScale]);

  // ------------------------------------------------------------ selection
  const linkProps = useMemo(() => new Map((data?.links.features ?? []).map((f) => [f.properties.id, f])), [data]);
  const selectedIds = useMemo(() => {
    const s = data?.streets.find((x) => x.street === street);
    return s?.directions.find((d) => d.heading === heading)?.linkIds ?? [];
  }, [data, street, heading]);
  const maxLanes = Math.max(0, ...selectedIds.map((id) => linkProps.get(id)?.properties.carLanes ?? 0));
  const originalLanes = useMemo<LaneKind[]>(() => Array.from({ length: maxLanes }, () => "car"), [maxLanes]);
  const existingBusLane = selectedIds.some((id) => linkProps.get(id)?.properties.busLane);
  const lanesSource = selectedIds.some((id) => linkProps.get(id)?.properties.lanesSource === "field check") ? "field check" : "osm";

  const select = useCallback((s: string | null, h: string | null) => {
    setScenario(null);
    setStreet(s);
    setHeading(h);
    setPinned(null);
    if (s && h) {
      setSidebarOpen(true);
      setPins((ps) => (ps.some((p) => p.street === s && p.heading === h) ? ps : [...ps, { street: s, heading: h, onMap: false }]));
    }
  }, []);

  useEffect(() => {
    const p = pendingScan.current;
    if (p && p.street === street && p.heading === heading) {
      pendingScan.current = null;
      setLanes(scanLanes(p, originalLanes));
      return;
    }
    const pl = pendingLanes.current;
    if (pl && pl.street === street && pl.heading === heading) {
      pendingLanes.current = null;
      if (pl.lanes.length === originalLanes.length) {
        setLanes(pl.lanes);
        return;
      }
    }
    setLanes(originalLanes);
  }, [originalLanes, street, heading]);

  // A scan row is applied exactly as it was tested: "removal" closes that one segment in both directions,
  // "lane" takes one car lane off every multi-lane link of the street direction (−1 lane in the mixer).
  const pickScan = useCallback((r: ScanRow) => {
    if (r.street === street && r.heading === heading) setLanes(scanLanes(r, originalLanes));
    else pendingScan.current = r;
    select(r.street, r.heading);
    if (r.kind === "removal") {
      setScenario(r);
      const coords = r.linkIds.map((id) => linkProps.get(id)?.geometry.coordinates ?? []).sort((a, b) => b.length - a.length)[0];
      if (coords && coords.length > 1) {
        setPinned({ coordinates: coords, color: "#c026d3", label: r.street, time: `${signed(r.changePct, 2)}%` });
      }
    }
  }, [select, street, heading, originalLanes, linkProps]);

  // a package closes several segments (and may take a lane for buses); no single street is selected
  const pickPackage = useCallback((r: ScanRow) => {
    setScenario(r);
    setSidebarOpen(true);
    const coords = r.linkIds.map((id) => linkProps.get(id)?.geometry.coordinates ?? []).sort((a, b) => b.length - a.length)[0];
    if (coords && coords.length > 1) setPinned({ coordinates: coords, color: "#c026d3", label: r.street, time: `${signed(r.changePct, 2)}%` });
  }, [linkProps]);

  const focusIds = scenario ? [...scenario.linkIds, ...(scenario.extraChanges ?? []).map((c) => c.linkId)] : selectedIds;

  // ------------------------------------------------------------ lanes → changes → live simulation
  const changes: Change[] = useMemo(() => {
    if (scenario) return [...scenario.linkIds.map((id) => ({ linkId: id, carLanesAfter: 0, use: "closed" as LaneUse })), ...(scenario.extraChanges ?? [])];
    const carAfter = lanes.filter((l) => l === "car").length;
    const removed = maxLanes - carAfter;
    if (removed <= 0) return [];
    const use: LaneUse = lanes.includes("bus") ? "bus" : lanes.includes("bike") ? "bike" : "sidewalk";
    return selectedIds
      .map((id) => {
        const n = linkProps.get(id)?.properties.carLanes ?? 0;
        // keep at least one car lane on narrower stretches unless the whole street goes car-free
        const after = carAfter === 0 ? 0 : Math.max(1, n - removed);
        return { linkId: id, carLanesAfter: Math.min(after, n), use: (after === 0 ? "closed" : use) as LaneUse };
      })
      .filter((c) => c.carLanesAfter < (linkProps.get(c.linkId)?.properties.carLanes ?? 0));
  }, [scenario, lanes, maxLanes, selectedIds, linkProps]);
  const changesKey = JSON.stringify(changes);

  // ------------------------------------------------------------ camera: whatever the user acts on is brought into view
  const coordsOf = useCallback((ids: string[]) => ids.flatMap((id) => linkProps.get(id)?.geometry.coordinates ?? []), [linkProps]);
  const focusCamera = useCallback((coords: LngLat[], mode: CameraTarget["mode"] = "fit") => {
    if (coords.length) setCamera((c) => ({ coords, mode, key: (c?.key ?? 0) + 1 }));
  }, []);
  const focusStr = focusIds.join(",");
  const focusStreet = scenario ? scenario.street : street;
  const lastFocus = useRef("");
  const lastStreet = useRef<string | null>(null);
  useEffect(() => {
    if (!focusIds.length) {
      lastFocus.current = "";
      lastStreet.current = null;
      return;
    }
    if (focusStr !== lastFocus.current) {
      // another street: fly to it. Same street (other direction, other side of an intersection,
      // a Braess-search closure being edited): only move if it is not already on screen
      const sameStreet = focusStreet !== null && focusStreet === lastStreet.current;
      lastFocus.current = focusStr;
      lastStreet.current = focusStreet;
      focusCamera(coordsOf(focusIds), sameStreet ? "ensure" : "fit");
    } else if (changes.length) {
      focusCamera(coordsOf(focusIds), "ensure");   // its lanes changed: move only if it is out of view
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusStr, changesKey]);

  // the floating panels cover parts of the map; the camera centres things in what is left
  const [vw, setVw] = useState(() => window.innerWidth);
  useEffect(() => {
    const onResize = () => setVw(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  const viewPadding: ViewPadding = useMemo(() => (vw < 768
    ? { top: 90, right: 24, bottom: 90, left: 24 }
    : { top: 96, right: recommendedOpen ? 408 : 60, bottom: 96, left: sidebarOpen ? 462 : 60 }), [vw, sidebarOpen, recommendedOpen]);

  // ------------------------------------------------------------ responsive layout (window width, px)
  //   < 768   phone: side panels take the full width, so the bottom controls hide while one is open
  //   < 1180  the two side panels do not fit next to each other: opening one closes the other
  //   < 1500  the side panels would run under the header pill, so they start below it
  const NARROW = 768;
  const BOTH_PANELS = 1180;
  const BESIDE_HEADER = 1500;
  const narrow = vw < NARROW;
  useEffect(() => {
    if (sidebarOpen && window.innerWidth < BOTH_PANELS) setRecommendedOpen(false);
  }, [sidebarOpen]);
  useEffect(() => {
    if (recommendedOpen && window.innerWidth < BOTH_PANELS) setSidebarOpen(false);
  }, [recommendedOpen]);
  useEffect(() => {
    // shrinking the window with both open: keep the street panel (the main workspace)
    if (vw < BOTH_PANELS) setRecommendedOpen((r) => (r && sidebarOpen ? false : r));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vw]);
  const belowHeader = vw < BESIDE_HEADER;
  // the part of the map no side panel covers: the layers panel, the time bar and the Braess pop-up live here
  const freeLeft = !narrow && sidebarOpen ? 434 : 12;
  const freeRight = !narrow && recommendedOpen ? 396 : 12;
  const panelCoversMap = narrow && (sidebarOpen || recommendedOpen);

  const ctrl = useRef<AbortController | null>(null);
  const autoDeltaFor = useRef("");
  useEffect(() => {
    ctrl.current?.abort();
    if (!changes.length) {
      autoDeltaFor.current = "";
      setResult(null);
      setBusy(false);
      return;
    }
    const c = new AbortController();
    ctrl.current = c;
    setBusy(true);
    const id = window.setTimeout(() => {
      api.simulate(changes, profile, demandScale, c.signal, evaporation)
        .then((r) => {
          setResult(r);
          // a new lane edit: show its effect (before/after colours); later time-of-day or demand changes keep the user's choice
          if (r.status === "ok" && autoDeltaFor.current !== changesKey) {
            autoDeltaFor.current = changesKey;
            setShowDelta(true);
          }
        })
        .catch((e: Error) => {
          if (e.name !== "AbortError") setError(e.message);
        })
        .finally(() => {
          if (!c.signal.aborted) setBusy(false);
        });
    }, 250);
    return () => {
      window.clearTimeout(id);
      c.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [changesKey, profile, demandScale, evaporation]);

  const ok = result && result.status === "ok" ? result : null;
  useEffect(() => {
    if (!ok) {
      setShowDelta(false);
      setPinned(null);
    }
  }, [ok]);

  // how congested the selected street is (animates the cars in the lane mixer)
  const slowness = useMemo(() => {
    const res = new Map((ok?.links ?? []).map((l) => [l.id, l]));
    const base = new Map((baseline ?? []).map((l) => [l.id, l]));
    let time = 0;
    let free = 0;
    for (const id of focusIds) {
      const r = res.get(id);
      const b = base.get(id);
      time += r ? r.timeAfterSec : b ? b.timeSec : 0;
      free += r ? r.freeTimeSec : b ? b.freeTimeSec : 0;
    }
    return free > 0 ? time / free : 1;
  }, [ok, baseline, focusIds]);

  // ------------------------------------------------------------ pins
  // live travel time of a street: under the current result if there is one, otherwise the base state
  const liveTimes = useCallback((pin: Pin): PinSnapshot => {
    const base = new Map((baseline ?? []).map((l) => [l.id, l.timeSec]));
    const res = new Map((ok?.links ?? []).map((l) => [l.id, l]));
    const ids = data?.streets.find((s) => s.street === pin.street)?.directions.find((d) => d.heading === pin.heading)?.linkIds ?? [];
    const sum = (f: (id: string) => number | undefined) => {
      let total = 0;
      for (const id of ids) {
        const v = f(id);
        if (v === undefined) return null;
        total += v;
      }
      return ids.length ? total : null;
    };
    return {
      beforeSec: ok ? sum((id) => res.get(id)?.timeBeforeSec) : sum((id) => base.get(id)),
      afterSec: ok ? sum((id) => res.get(id)?.timeAfterSec) : null,
    };
  }, [data, baseline, ok]);
  // a street pinned while its lanes were changed shows the before → after of that change, not the live time
  const pinTimes: PinTime[] = useMemo(() => pins.map((pin) => ({ pin, ...(pin.snapshot ?? liveTimes(pin)) })), [pins, liveTimes]);

  // "−1 car lane → Bus" for a remembered change (null when nothing was changed)
  const changeLabel = useCallback((pin: Pin): string | null => {
    const l = pin.snapshot?.lanes;
    if (!l || !l.length) return null;
    const taken = l.filter((k) => k !== "car");
    if (!taken.length) return null;
    if (taken.length === l.length) return t.pinClosed;
    const kinds = [...new Set(taken)].map((k) => t.laneKinds[k]).join(", ");
    return t.pinLaneChange.replace("{n}", String(taken.length)).replace("{kinds}", kinds);
  }, [t]);

  // pinned + being edited: keep its remembered change up to date with the latest result
  const isEditing = useCallback((p: Pin) => p.street === street && p.heading === heading, [street, heading]);
  useEffect(() => {
    if (!ok || !changes.length) return;
    setPins((ps) => {
      let touched = false;
      const next = ps.map((p) => {
        if (!p.onMap || !isEditing(p)) return p;
        const live = { ...liveTimes(p), lanes };
        if (p.snapshot && p.snapshot.beforeSec === live.beforeSec && p.snapshot.afterSec === live.afterSec
          && p.snapshot.lanes?.join() === lanes.join()) return p;
        touched = true;
        return { ...p, snapshot: live };
      });
      return touched ? next : ps;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ok]);

  // on the map: the street being edited, plus the ones pinned with the pin button in the list
  const mapPins: MapPinView[] = useMemo(() => pinTimes
    .filter(({ pin }) => pin.onMap || (pin.street === street && pin.heading === heading))
    .map(({ pin, beforeSec, afterSec }) => {
      const ids = data?.streets.find((s) => s.street === pin.street)?.directions.find((d) => d.heading === pin.heading)?.linkIds ?? [];
      const longest = ids.map((id) => linkProps.get(id)).filter((f): f is NonNullable<typeof f> => !!f)
        .sort((a, b) => b.properties.lengthM - a.properties.lengthM)[0];
      const g = longest?.geometry.coordinates ?? [];
      const at: LngLat = g.length ? g[Math.floor(g.length / 2)] : [0, 0];
      const change = changeLabel(pin);
      return { key: pinKey(pin), label: `${pin.street} · ${t.heading[pin.heading] ?? pin.heading}${change ? ` · ${change}` : ""}`, at, beforeSec, afterSec };
    }), [pinTimes, data, linkProps, t, street, heading, changeLabel]);
  const togglePinOnMap = useCallback((p: Pin) => {
    // pinning the street whose lanes are being changed captures that change (shown until the row is removed)
    const capture = !p.onMap && isEditing(p) && !!ok && changes.length > 0 ? { ...liveTimes(p), lanes } : null;
    setPins((ps) => ps.map((x) => (pinKey(x) === pinKey(p) ? { ...x, onMap: !x.onMap, snapshot: capture ?? x.snapshot } : x)));
  }, [isEditing, ok, changes.length, liveTimes, lanes]);

  // clicking a pin shows that street again, with the lanes it was pinned with
  const openPin = useCallback((p: Pin) => {
    const l = p.snapshot?.lanes;
    if (p.street === street && p.heading === heading) {
      setScenario(null);
      if (l && l.length === originalLanes.length) setLanes(l);
      return;
    }
    pendingLanes.current = l ? { street: p.street, heading: p.heading, lanes: l } : null;
    select(p.street, p.heading);
  }, [street, heading, originalLanes, select]);

  const pickLink = useCallback((id: string) => {
    const f = linkProps.get(id);
    if (!f || !data) return;
    const p = f.properties;
    const s = data.streets.find((x) => x.street === p.street);
    if (s && s.directions.some((d) => d.heading === p.heading)) select(p.street, p.heading);
  }, [linkProps, data, select]);
  // clicking empty map: nothing selected any more (the search box empties with it)
  const deselect = useCallback(() => select(null, null), [select]);

  const isDark = mapTheme === "dark";

  return (
    <I18nContext.Provider value={i18n}>
      <div className={`relative h-screen w-screen overflow-clip transition-colors duration-300 ${!narrow && recommendedOpen ? "right-panel-open" : ""} ${isDark ? "theme-dark bg-[#0B1120] text-slate-100" : "bg-[#F8FAFC] text-[#0F172A]"}`}>
        {data && (
          <CorridorMap data={data} baseline={baseline} baselineJunctions={baselineJunctions} result={ok} scanRows={scanRows}
            layers={layers} mapTheme={mapTheme} showDelta={showDelta} selectedLinkIds={focusIds} pins={mapPins}
            highlight={hovered ?? pinned} camera={camera} viewPadding={viewPadding} highlightBus={hoverBus} onPickLink={pickLink} onPickNothing={deselect} />
        )}

        {/* top-center pill header */}
        <header className="glass pointer-events-auto absolute left-1/2 top-3 z-30 flex w-[min(640px,calc(100vw-24px))] -translate-x-1/2 items-center justify-between gap-3 rounded-full px-4 py-3 sm:gap-6 sm:px-6">
          <img
            src={isDark ? "/pmt-logo-dark.png" : "/pmt-logo.png"}
            alt="Primăria Municipiului Timișoara"
            className={`h-8 w-auto shrink-0 select-none object-contain sm:h-10 ${isDark ? "" : "mix-blend-multiply"}`}
          />
          <h1 className={`min-w-0 truncate text-[15px] font-bold leading-tight tracking-tight sm:text-[17px] ${isDark ? "text-slate-100" : "text-[#0F172A]"}`}>
            {t.pillTitle}
          </h1>
          <div className="flex shrink-0 items-center gap-2">
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-label="Menu"
                className={`grid h-9 w-9 place-items-center rounded-full shadow-sm transition duration-200 active:scale-95 ${
                  isDark
                    ? `bg-slate-800 text-[#38BDF8] hover:bg-slate-700 ${menuOpen ? "ring-2 ring-[#38BDF8]" : "border border-slate-700"}`
                    : `bg-white text-[#005BBC] hover:bg-slate-50 ${menuOpen ? "ring-2 ring-[#005BBC]" : "border border-slate-200/80"}`
                }`}
              >
                {/* the hamburger turns into a close icon while the menu is open */}
                <span className="relative grid h-[18px] w-[18px] place-items-center" aria-hidden="true">
                  <Menu size={18} strokeWidth={2.2}
                    className={`absolute transition duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${menuOpen ? "rotate-90 scale-50 opacity-0" : "rotate-0 scale-100 opacity-100"}`} />
                  <X size={18} strokeWidth={2.2}
                    className={`absolute transition duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${menuOpen ? "rotate-0 scale-100 opacity-100" : "-rotate-90 scale-50 opacity-0"}`} />
                </span>
              </button>

              {menu.mounted && (
                <div
                  role="menu"
                  className={`absolute right-0 top-full z-30 mt-2 flex w-60 origin-top-right flex-col gap-1 rounded-xl border p-1.5 shadow-island ${
                    menu.closing ? "pointer-events-none m-pop-out" : "m-pop-in"
                  } ${isDark ? "border-slate-700/90 bg-slate-900" : "border-slate-200/90 bg-white"}`}
                >
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setSidebarOpen((open) => !open);
                      setMenuOpen(false);
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition active:scale-[0.98] ${
                      isDark ? "bg-slate-900 text-slate-100 hover:bg-slate-800" : "bg-white text-[#0F172A] hover:bg-slate-50"
                    } ${sidebarOpen ? (isDark ? "ring-1 ring-[#38BDF8]/45" : "ring-1 ring-[#005BBC]/35") : ""}`}
                  >
                    <Search size={16} className={`shrink-0 ${isDark ? "text-[#38BDF8]" : "text-[#005BBC]"}`} strokeWidth={2.2} />
                    <span className="truncate">{t.menuSearchPoints}</span>
                  </button>

                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setRecommendedOpen((open) => !open);
                      setMenuOpen(false);
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition active:scale-[0.98] ${
                      isDark ? "bg-slate-900 text-slate-100 hover:bg-slate-800" : "bg-white text-[#0F172A] hover:bg-slate-50"
                    } ${recommendedOpen ? (isDark ? "ring-1 ring-[#10B981]/50" : "ring-1 ring-[#059669]/40") : ""}`}
                  >
                    <Leaf size={16} className={`shrink-0 ${isDark ? "text-[#10B981]" : "text-[#059669]"}`} strokeWidth={2.2} />
                    <span className="truncate">{t.menuRecommendedPoints}</span>
                  </button>

                  <div className="relative">
                    <button
                      type="button"
                      role="menuitem"
                      aria-expanded={themeMenuOpen}
                      onClick={() => setThemeMenuOpen((open) => !open)}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition active:scale-[0.98] ${
                        isDark ? "bg-slate-900 text-slate-100 hover:bg-slate-800" : "bg-white text-[#0F172A] hover:bg-slate-50"
                      } ${themeMenuOpen ? (isDark ? "ring-1 ring-[#38BDF8]/45" : "ring-1 ring-[#005BBC]/35") : ""}`}
                    >
                      <Palette size={16} className={`shrink-0 ${isDark ? "text-[#38BDF8]" : "text-[#005BBC]"}`} strokeWidth={2.2} />
                      <span className="truncate">{t.menuTheme}</span>
                    </button>

                    {themeMenu.mounted && (
                      // centred by a static flex wrapper: the slide-in animation sets `transform`,
                      // which used to cancel a -translate-y-1/2 and make the flyout jump when it appeared
                      <div className={`absolute inset-y-0 left-full z-40 ml-2 flex items-center ${themeMenu.closing ? "pointer-events-none" : ""}`}>
                      <div
                        role="group"
                        aria-label={t.menuTheme}
                        className={`flex items-center gap-1.5 rounded-xl border p-1.5 shadow-island ${themeMenu.closing ? "m-side-out" : "m-side-in"} ${
                          isDark ? "border-slate-700/90 bg-slate-900" : "border-slate-200/90 bg-white"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => withViewTransition(() => setMapTheme("dark"))}
                          aria-label={t.themeDark}
                          title={t.themeDark}
                          aria-pressed={mapTheme === "dark"}
                          className={`grid h-9 w-9 place-items-center rounded-lg transition hover:scale-105 ${
                            isDark ? "bg-slate-800" : "bg-white"
                          } ${mapTheme === "dark" ? (isDark ? "ring-2 ring-[#38BDF8] shadow-sm" : "ring-2 ring-[#005BBC] shadow-sm") : "opacity-80 hover:opacity-100"}`}
                        >
                          <DarkMapIcon />
                        </button>

                        <button
                          type="button"
                          onClick={() => withViewTransition(() => setMapTheme("colored"))}
                          aria-label={t.themeColored}
                          title={t.themeColored}
                          aria-pressed={mapTheme === "colored"}
                          className={`grid h-9 w-9 place-items-center rounded-lg transition hover:scale-105 ${
                            isDark ? "bg-slate-800" : "bg-white"
                          } ${mapTheme === "colored" ? (isDark ? "ring-2 ring-[#38BDF8] shadow-sm" : "ring-2 ring-[#005BBC] shadow-sm") : "opacity-80 hover:opacity-100"}`}
                        >
                          <ColoredMapIcon />
                        </button>

                        <button
                          type="button"
                          onClick={() => setLayers((l) => ({ ...l, buildings3d: !l.buildings3d }))}
                          aria-label={t.theme3d}
                          title={t.theme3d}
                          aria-pressed={layers.buildings3d}
                          className={`flex h-9 w-9 flex-col items-center justify-center gap-0.5 rounded-lg transition hover:scale-105 active:scale-95 ${
                            layers.buildings3d
                              ? isDark
                                ? "bg-sky-950/80 text-[#38BDF8] ring-2 ring-[#38BDF8] shadow-sm"
                                : "bg-blue-50/80 text-[#005BBC] ring-2 ring-[#005BBC] shadow-sm"
                              : isDark
                                ? "bg-slate-800 text-slate-400 hover:text-[#38BDF8]"
                                : "bg-slate-50 text-slate-400 hover:text-[#005BBC]"
                          }`}
                        >
                          <Box size={15} strokeWidth={2.2} />
                          <span className="text-[8.5px] font-bold leading-none">3D</span>
                        </button>
                      </div>
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setExplainer(true);
                      setMenuOpen(false);
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition active:scale-[0.98] ${
                      isDark ? "bg-slate-900 text-slate-100 hover:bg-slate-800" : "bg-white text-[#0F172A] hover:bg-slate-50"
                    }`}
                  >
                    <HelpCircle size={16} className={`shrink-0 ${isDark ? "text-[#38BDF8]" : "text-[#005BBC]"}`} strokeWidth={2.2} />
                    <span className="truncate">{t.menuExplanation}</span>
                  </button>
                </div>
              )}
            </div>

            <div ref={langThumb.ref} className={`relative flex rounded-full p-0.5 font-secondary text-[11px] ${isDark ? "bg-slate-800" : "bg-slate-100"}`} role="radiogroup" aria-label={t.language}>
              <span aria-hidden="true" style={langThumb.style}
                className={`absolute left-0 top-0 rounded-full shadow-sm transition-[transform,width,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${isDark ? "bg-slate-700" : "bg-white"}`} />
              {(["ro", "en"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  role="radio"
                  data-thumb-key={l}
                  aria-checked={lang === l}
                  onClick={() => withViewTransition(() => setLang(l))}
                  className={`relative rounded-full px-2.5 py-1 font-semibold uppercase transition-colors duration-300 ${
                    lang === l
                      ? isDark
                        ? "text-[#38BDF8]"
                        : "text-[#005BBC]"
                      : isDark
                        ? "text-slate-400 hover:text-slate-200"
                        : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>
        </header>

        {/* floating glass sidebar */}
        <aside
          aria-hidden={!sidebarOpen}
          className={`glass absolute bottom-3 left-3 z-20 flex w-[410px] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl transition-[transform,opacity,top] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
            belowHeader ? "top-[88px]" : "top-3"
          } ${
            sidebarOpen
              ? "pointer-events-auto translate-x-0 opacity-100"
              : "pointer-events-none -translate-x-[calc(100%+24px)] opacity-0"
          }`}
        >
          <header className="flex items-center gap-2 border-b border-slate-200/80 px-4 py-3">
            <div className="min-w-0 flex-1">
              <h2 className="text-[15px] font-bold leading-tight tracking-tight">{t.menuSearchPoints}</h2>
            </div>
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
              title={t.close}
              aria-label={t.close}
            >
              <X size={17} />
            </button>
          </header>

          <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
            {error && (
              <div className="m-rise-in rounded-xl border border-red-200 bg-red-50 p-3 text-[12.5px] text-red-800">
                {t.backendDown}
                <p className="mt-1 font-secondary text-[11px]">{error}</p>
                <button onClick={() => setReload((r) => r + 1)} className="mt-2 flex items-center gap-1 rounded bg-white px-2 py-1 text-[12px] shadow-sm">
                  <RefreshCw size={12} /> {t.retry}
                </button>
              </div>
            )}
            {!data && !error && <p className="m-fade-in flex items-center gap-2 text-[13px] text-slate-500"><Loader2 size={15} className="animate-spin" /> {t.loading}</p>}
            {data && (
              <>
                <StreetSearch data={data} street={street} heading={heading} onChange={select} />
                {scenario && (
                  <section key={scenario.linkIds.join(",")} className="m-rise-in rounded-xl border border-fuchsia-300 bg-fuchsia-50 p-3">
                    <p className="text-[11.5px] font-semibold text-fuchsia-700">{t.scenarioTitle}</p>
                    <p className="mt-0.5 text-[12.5px] font-semibold text-slate-900">{scenario.kind === "package" ? t.scenarioPackage : t.scenarioClosed}</p>
                    <p className="text-[11.5px] text-slate-600">
                      {scenario.kind === "package"
                        ? <>{scenario.street}{scenario.fromName && <> + {t.pkgLaneBus} {scenario.fromName}</>}</>
                        : <>{scenario.street}: {scenario.fromName} → {scenario.toName}</>}
                    </p>
                    <button type="button" onClick={() => setScenario(null)}
                      className="mt-1.5 flex items-center gap-1 rounded-md bg-white px-2 py-1 text-[11.5px] font-semibold text-[#005BBC] shadow-sm hover:bg-slate-50">
                      <Undo2 size={12} /> {t.scenarioUndo}
                    </button>
                  </section>
                )}
                {selectedIds.length > 0 && (
                  // keyed by street so picking another street replays the lanes' entrance
                  <LaneMixer key={`${street}|${heading}`} lanes={lanes} original={originalLanes} existingBusLane={existingBusLane} segments={selectedIds.length}
                    lanesSource={lanesSource} slowness={slowness} busy={busy}
                    onChange={(l) => { setScenario(null); setLanes(l); }} />
                )}
                <PinsPanel times={pinTimes} onTogglePin={togglePinOnMap} onOpen={openPin} changeLabel={changeLabel}
                  onRemove={(p) => setPins((ps) => ps.filter((x) => pinKey(x) !== pinKey(p)))} />
                <ResultsPanel result={result} changes={changes} profile={profile} busy={busy} tripCosts={data.tripCosts} profiles={data.profiles}
                  evaporation={evaporation} onEvaporation={setEvaporation} evapOptions={data.evaporation} onProfile={setProfile} onHoverBus={setHoverBus}
                  onHighlight={setHovered} onFocus={(h) => { setPinned(h); focusCamera([...h.coordinates, ...(h.ghost ?? [])], "fit"); }} />
                <SourcesNote data={data} />
              </>
            )}
          </div>
        </aside>

        {/* right "Optimized ways" panel: the same glass panel as the street panel on the left (header + scrolling body) */}
        <aside
          aria-hidden={!recommendedOpen}
          className={`glass absolute bottom-3 right-3 z-20 flex w-[372px] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl transition-[transform,opacity,top] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
            belowHeader ? "top-[88px]" : "top-3"
          } ${
            recommendedOpen
              ? "pointer-events-auto translate-x-0 opacity-100"
              : "pointer-events-none translate-x-[calc(100%+24px)] opacity-0"
          }`}
        >
          <ScanCard
            rows={scanRows}
            loading={scanLoading}
            stats={scanStats}
            demandScale={demandScale}
            onPick={pickScan}
            onClose={() => setRecommendedOpen(false)}
            pkg={pkg}
            onPickPackage={pickPackage}
          />
        </aside>

        {/* free part of the map (between the open side panels, under the header). Its bottom row holds the layers panel and
            the time bar: side by side when there is room, stacked (time bar at the very bottom) when there is not.
            row-reverse + wrap-reverse makes the time bar the first item of the bottom line; mr-auto keeps the layers panel left. */}
        <div
          className={`pointer-events-none absolute bottom-3 top-[88px] z-10 flex flex-col justify-end transition-[left,right] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
            panelCoversMap ? "hidden" : ""
          }`}
          style={{ left: freeLeft, right: freeRight }}
        >
          {/* (with wrap-reverse the cross axis is flipped too, so items-start is what lines up the bottoms) */}
          <div className="flex flex-row-reverse flex-wrap-reverse items-start gap-2">
            {data && data.profiles.length > 0 && (
              // leaves room on the right for the map's zoom buttons
              <div className="flex min-w-0 flex-[1_1_280px] justify-center pr-11">
                <ProfileBar profiles={data.profiles} profile={profile} demandScale={demandInput}
                  demandVehH={demandVehH} onChange={setProfile} onDemandScale={setDemandInput} />
              </div>
            )}
            <div className="mr-auto max-w-full">
              <LayersPill layers={layers} onChange={setLayers} showDelta={showDelta} onShowDelta={setShowDelta} hasResult={!!ok}
                open={layersOpen} onOpenChange={setLayersOpen} />
            </div>
          </div>
        </div>
      </div>
      <CitizenBraessExplainerModal open={explainer} onClose={() => setExplainer(false)} />
    </I18nContext.Provider>
  );
}
