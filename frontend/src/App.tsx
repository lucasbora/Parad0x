import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Box, HelpCircle, Leaf, Loader2, Menu, Palette, RefreshCw, Search, Undo2, X } from "lucide-react";
import { api, signed } from "./api";
import { I18nContext, translations, type Lang } from "./i18n/translations";
import type {
  BaselineLink,
  BusResult,
  CalibrationResponse,
  Change,
  CorridorResponse,
  DemandSource,
  DemandSummary,
  Highlight,
  LaneKind,
  LaneUse,
  LngLat,
  MapLayers,
  Pin,
  Profile,
  ScanRow,
  SimulateResponse,
} from "./types/corridor";
import CorridorMap, { type MapPinView, type MapTheme } from "./components/CorridorMap";
import LayersPill from "./components/LayersPill";
import DataStatusCard from "./components/DataStatusCard";
import StreetSearch from "./components/StreetSearch";
import LaneMixer from "./components/LaneMixer";
import PinsPanel, { type PinTime } from "./components/PinsPanel";
import ScanCard from "./components/ScanCard";
import ResultsPanel from "./components/ResultsPanel";
import ModelCheckCard from "./components/ModelCheckCard";
import BraessToast from "./components/BraessToast";
import ProfileBar from "./components/ProfileBar";
import CitizenBraessExplainerModal from "./components/CitizenBraessExplainerModal";

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
  const [calibration, setCalibration] = useState<CalibrationResponse | null>(null);
  const [profile, setProfile] = useState<Profile>("morning");
  const [demandSource, setDemandSource] = useState<DemandSource | null>(null);
  const [demandSummary, setDemandSummary] = useState<DemandSummary | null>(null);
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

  const [street, setStreet] = useState<string | null>(null);
  const [heading, setHeading] = useState<string | null>(null);
  const [lanes, setLanes] = useState<LaneKind[]>([]);
  const pendingScan = useRef<ScanRow | null>(null);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [pins, setPins] = useState<Pin[]>([]);
  const [layers, setLayers] = useState<MapLayers>(DEFAULT_LAYERS);
  const [showDelta, setShowDelta] = useState(false);
  const [hoverBus, setHoverBus] = useState<BusResult | null>(null);
  const [hovered, setHovered] = useState<Highlight | null>(null);
  const [pinned, setPinned] = useState<Highlight | null>(null);
  const [focusKey, setFocusKey] = useState(0);
  const [toastPct, setToastPct] = useState<number | null>(null);
  const [explainer, setExplainer] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [recommendedOpen, setRecommendedOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);
  const [mapTheme, setMapTheme] = useState<MapTheme>("colored");
  const menuRef = useRef<HTMLDivElement | null>(null);

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
    setCalibration(null);
    setScanLoading(true);
    api.scan(profile).then((s) => {
      if (!live) return;
      setScanRows(s.status === "ok" ? s.rows : null);
      setScanStats(s.status === "ok" ? { tested: s.tested.removal + s.tested.lane, seconds: s.seconds } : null);
    }).catch(() => undefined)
      .finally(() => live && setScanLoading(false));
    api.calibration(profile).then((c) => live && setCalibration(c)).catch(() => undefined);
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
      setDemandSource(b.demandSource);
      setDemandSummary(b.demandSummary);
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
      setPins((ps) => (ps.some((p) => p.street === s && p.heading === h) ? ps : [...ps, { street: s, heading: h }]));
    }
  }, []);

  useEffect(() => {
    const p = pendingScan.current;
    if (p && p.street === street && p.heading === heading) {
      pendingScan.current = null;
      setLanes(scanLanes(p, originalLanes));
      return;
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
        setFocusKey((k) => k + 1);
      }
    }
  }, [select, street, heading, originalLanes, linkProps]);

  const focusIds = scenario ? scenario.linkIds : selectedIds;

  // ------------------------------------------------------------ lanes → changes → live simulation
  const changes: Change[] = useMemo(() => {
    if (scenario) return scenario.linkIds.map((id) => ({ linkId: id, carLanesAfter: 0, use: "closed" as LaneUse }));
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

  const ctrl = useRef<AbortController | null>(null);
  useEffect(() => {
    ctrl.current?.abort();
    if (!changes.length) {
      setResult(null);
      setBusy(false);
      return;
    }
    const c = new AbortController();
    ctrl.current = c;
    setBusy(true);
    const id = window.setTimeout(() => {
      api.simulate(changes, profile, demandScale, c.signal)
        .then((r) => {
          setResult(r);
          if (r.status === "ok" && r.braess.detected) setToastPct(r.braess.totalChangePct);
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
  }, [changesKey, profile, demandScale]);

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
  const pinTimes: PinTime[] = useMemo(() => {
    const base = new Map((baseline ?? []).map((l) => [l.id, l.timeSec]));
    const res = new Map((ok?.links ?? []).map((l) => [l.id, l]));
    return pins.map((pin) => {
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
        pin,
        beforeSec: ok ? sum((id) => res.get(id)?.timeBeforeSec) : sum((id) => base.get(id)),
        afterSec: ok ? sum((id) => res.get(id)?.timeAfterSec) : null,
      };
    });
  }, [pins, data, baseline, ok]);

  const mapPins: MapPinView[] = useMemo(() => pinTimes.map(({ pin, beforeSec, afterSec }) => {
    const ids = data?.streets.find((s) => s.street === pin.street)?.directions.find((d) => d.heading === pin.heading)?.linkIds ?? [];
    const longest = ids.map((id) => linkProps.get(id)).filter((f): f is NonNullable<typeof f> => !!f)
      .sort((a, b) => b.properties.lengthM - a.properties.lengthM)[0];
    const g = longest?.geometry.coordinates ?? [];
    const at: LngLat = g.length ? g[Math.floor(g.length / 2)] : [0, 0];
    return { key: pinKey(pin), label: `${pin.street} · ${t.heading[pin.heading] ?? pin.heading}`, at, beforeSec, afterSec };
  }), [pinTimes, data, linkProps, t]);

  const pickLink = useCallback((id: string) => {
    const f = linkProps.get(id);
    if (!f || !data) return;
    const p = f.properties;
    const s = data.streets.find((x) => x.street === p.street);
    if (s && s.directions.some((d) => d.heading === p.heading)) select(p.street, p.heading);
  }, [linkProps, data, select]);

  const isDark = mapTheme === "dark";

  return (
    <I18nContext.Provider value={i18n}>
      <div className={`relative h-screen w-screen overflow-hidden transition-colors duration-300 ${isDark ? "theme-dark bg-[#0B1120] text-slate-100" : "bg-[#F8FAFC] text-[#0F172A]"}`}>
        {data && (
          <CorridorMap data={data} baseline={baseline} baselineJunctions={baselineJunctions} result={ok} scanRows={scanRows}
            layers={layers} mapTheme={mapTheme} showDelta={showDelta} selectedLinkIds={focusIds} pins={mapPins}
            highlight={hovered ?? pinned} focusKey={focusKey} highlightBus={hoverBus} onPickLink={pickLink} />
        )}

        {/* top-center pill header */}
        <header className="glass pointer-events-auto absolute left-1/2 top-3 z-20 flex w-[min(640px,calc(100vw-24px))] -translate-x-1/2 items-center justify-between gap-6 rounded-full px-6 py-3">
          <img
            src={isDark ? "/pmt-logo-dark.png" : "/pmt-logo.png"}
            alt="Primăria Municipiului Timișoara"
            className={`h-10 w-auto shrink-0 select-none object-contain ${isDark ? "" : "mix-blend-multiply"}`}
          />
          <h1 className={`whitespace-nowrap text-[17px] font-bold leading-tight tracking-tight ${isDark ? "text-slate-100" : "text-[#0F172A]"}`}>
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
                className={`grid h-9 w-9 place-items-center rounded-full shadow-sm transition duration-200 ${
                  isDark
                    ? `bg-slate-800 text-[#38BDF8] hover:bg-slate-700 ${menuOpen ? "ring-2 ring-[#38BDF8]" : "border border-slate-700"}`
                    : `bg-white text-[#005BBC] hover:bg-slate-50 ${menuOpen ? "ring-2 ring-[#005BBC]" : "border border-slate-200/80"}`
                }`}
              >
                <Menu size={18} strokeWidth={2.2} />
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  className={`absolute right-0 top-full z-30 mt-2 flex w-60 flex-col gap-1 rounded-xl border p-1.5 shadow-island animate-slideIn ${
                    isDark ? "border-slate-700/90 bg-slate-900" : "border-slate-200/90 bg-white"
                  }`}
                >
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setExplainer(true);
                      setMenuOpen(false);
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition ${
                      isDark ? "bg-slate-900 text-slate-100 hover:bg-slate-800" : "bg-white text-[#0F172A] hover:bg-slate-50"
                    }`}
                  >
                    <HelpCircle size={16} className={`shrink-0 ${isDark ? "text-[#38BDF8]" : "text-[#005BBC]"}`} strokeWidth={2.2} />
                    <span className="truncate">{t.menuExplanation}</span>
                  </button>

                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setSidebarOpen((open) => !open);
                      setMenuOpen(false);
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition ${
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
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition ${
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
                      className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[12.5px] font-semibold transition ${
                        isDark ? "bg-slate-900 text-slate-100 hover:bg-slate-800" : "bg-white text-[#0F172A] hover:bg-slate-50"
                      } ${themeMenuOpen ? (isDark ? "ring-1 ring-[#38BDF8]/45" : "ring-1 ring-[#005BBC]/35") : ""}`}
                    >
                      <Palette size={16} className={`shrink-0 ${isDark ? "text-[#38BDF8]" : "text-[#005BBC]"}`} strokeWidth={2.2} />
                      <span className="truncate">{t.menuTheme}</span>
                    </button>

                    {themeMenuOpen && (
                      <div
                        role="group"
                        aria-label={t.menuTheme}
                        className={`absolute left-full top-1/2 z-40 ml-2 flex -translate-y-1/2 items-center gap-1.5 rounded-xl border p-1.5 shadow-island animate-slideIn ${
                          isDark ? "border-slate-700/90 bg-slate-900" : "border-slate-200/90 bg-white"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => setMapTheme("dark")}
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
                          onClick={() => setMapTheme("colored")}
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
                          className={`grid h-9 w-9 place-items-center rounded-lg transition hover:scale-105 ${
                            layers.buildings3d
                              ? isDark
                                ? "bg-sky-950/80 text-[#38BDF8] ring-2 ring-[#38BDF8] shadow-sm"
                                : "bg-blue-50/80 text-[#005BBC] ring-2 ring-[#005BBC] shadow-sm"
                              : isDark
                                ? "bg-slate-800 text-slate-400 hover:text-[#38BDF8]"
                                : "bg-slate-50 text-slate-400 hover:text-[#005BBC]"
                          }`}
                        >
                          <Box size={19} strokeWidth={2.2} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className={`flex rounded-full p-0.5 font-mono text-[11px] ${isDark ? "bg-slate-800" : "bg-slate-100"}`} role="radiogroup" aria-label={t.language}>
              {(["ro", "en"] as const).map((l) => (
                <button
                  key={l}
                  type="button"
                  role="radio"
                  aria-checked={lang === l}
                  onClick={() => setLang(l)}
                  className={`rounded-full px-2.5 py-1 font-semibold uppercase transition ${
                    lang === l
                      ? isDark
                        ? "bg-slate-700 text-[#38BDF8] shadow-sm"
                        : "bg-white text-[#005BBC] shadow-sm"
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
          className={`glass absolute bottom-3 left-3 top-3 z-10 flex w-[410px] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl transition-[transform,opacity] duration-300 ease-out ${
            sidebarOpen
              ? "pointer-events-auto translate-x-0 opacity-100"
              : "pointer-events-none -translate-x-[calc(100%+24px)] opacity-0"
          }`}
        >
          <header className="flex items-center gap-2 border-b border-slate-200/80 px-4 py-3">
            <div className="min-w-0 flex-1">
              <h2 className="text-[15px] font-bold leading-tight tracking-tight">{t.appName}</h2>
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
              <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-[12.5px] text-red-800">
                {t.backendDown}
                <p className="mt-1 font-mono text-[11px]">{error}</p>
                <button onClick={() => setReload((r) => r + 1)} className="mt-2 flex items-center gap-1 rounded bg-white px-2 py-1 text-[12px] shadow-sm">
                  <RefreshCw size={12} /> {t.retry}
                </button>
              </div>
            )}
            {!data && !error && <p className="flex items-center gap-2 text-[13px] text-slate-500"><Loader2 size={15} className="animate-spin" /> {t.loading}</p>}
            {data && (
              <>
                <DataStatusCard data={data} profile={profile} demand={demandSummary} />
                <StreetSearch data={data} street={street} heading={heading} onChange={select} />
                {scenario && (
                  <section className="rounded-xl border border-fuchsia-300 bg-fuchsia-50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-fuchsia-700">{t.scenarioTitle}</p>
                    <p className="mt-0.5 text-[12.5px] font-semibold text-slate-900">{t.scenarioClosed}</p>
                    <p className="text-[11.5px] text-slate-600">{scenario.street}: {scenario.fromName} → {scenario.toName}</p>
                    <button type="button" onClick={() => setScenario(null)}
                      className="mt-1.5 flex items-center gap-1 rounded-md bg-white px-2 py-1 text-[11.5px] font-semibold text-[#005BBC] shadow-sm hover:bg-slate-50">
                      <Undo2 size={12} /> {t.scenarioUndo}
                    </button>
                  </section>
                )}
                {selectedIds.length > 0 && (
                  <LaneMixer lanes={lanes} original={originalLanes} existingBusLane={existingBusLane} segments={selectedIds.length}
                    lanesSource={lanesSource} slowness={slowness} busy={busy}
                    onChange={(l) => { setScenario(null); setLanes(l); }} />
                )}
                <PinsPanel times={pinTimes} onRemove={(p) => setPins((ps) => ps.filter((x) => pinKey(x) !== pinKey(p)))} />
                <ResultsPanel result={result} changes={changes} profile={profile} onHoverBus={setHoverBus}
                  onHighlight={setHovered} onFocus={(h) => { setPinned(h); setFocusKey((k) => k + 1); }} />
                <ModelCheckCard data={data} calibration={calibration} />
              </>
            )}
          </div>
        </aside>

        {/* top-right Recommended Points floating panel */}
        <aside
          aria-hidden={!recommendedOpen}
          className={`absolute right-3 top-3 z-10 w-[360px] max-w-[calc(100vw-24px)] max-h-[calc(100vh-80px)] overflow-y-auto transition-[transform,opacity] duration-300 ease-out ${
            recommendedOpen
              ? "pointer-events-auto translate-x-0 opacity-100"
              : "pointer-events-none translate-x-[calc(100%+24px)] opacity-0"
          }`}
        >
          <ScanCard
            rows={scanRows}
            loading={scanLoading}
            demandSource={demandSource}
            stats={scanStats}
            demandScale={demandScale}
            onPick={pickScan}
            onClose={() => setRecommendedOpen(false)}
          />
        </aside>

        <div
          className={`pointer-events-none absolute bottom-3 z-10 hidden transition-[left] duration-300 ease-out md:block ${
            sidebarOpen ? "left-[436px]" : "left-3"
          }`}
        >
          <LayersPill layers={layers} onChange={setLayers} showDelta={showDelta} onShowDelta={setShowDelta} hasResult={!!ok} />
        </div>

        {/* bottom bar: time of day + demand level, centred in the free space right of the layers pill */}
        {data && data.profiles.length > 0 && (
          <div
            className={`pointer-events-none absolute bottom-3 right-14 z-20 flex justify-center transition-[left] duration-300 ease-out ${
              sidebarOpen ? "left-3 md:left-[712px]" : "left-3 md:left-[288px]"
            }`}
          >
            <ProfileBar profiles={data.profiles} profile={profile} demandSource={demandSource} demandScale={demandInput}
              demandVehH={demandVehH} onChange={setProfile} onDemandScale={setDemandInput} />
          </div>
        )}

        <BraessToast changePct={toastPct} estimated={demandSource === "estimated"} onClose={() => setToastPct(null)} />
      </div>
      <CitizenBraessExplainerModal open={explainer} onClose={() => setExplainer(false)} />
    </I18nContext.Provider>
  );
}
