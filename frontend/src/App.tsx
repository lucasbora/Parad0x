import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { HelpCircle, Loader2, RefreshCw } from "lucide-react";
import { api } from "./api";
import { I18nContext, translations, type Lang } from "./i18n/translations";
import type {
  BaselineLink,
  BusResult,
  CalibrationResponse,
  Change,
  CorridorResponse,
  Highlight,
  LaneKind,
  LaneUse,
  LngLat,
  MapLayers,
  Pin,
  ScanRow,
  SimulateResponse,
} from "./types/corridor";
import CorridorMap, { type MapPinView } from "./components/CorridorMap";
import LayersPill from "./components/LayersPill";
import DataStatusCard from "./components/DataStatusCard";
import StreetSearch from "./components/StreetSearch";
import LaneMixer from "./components/LaneMixer";
import PinsPanel, { type PinTime } from "./components/PinsPanel";
import ScanCard from "./components/ScanCard";
import ResultsPanel from "./components/ResultsPanel";
import ModelCheckCard from "./components/ModelCheckCard";
import BraessToast from "./components/BraessToast";
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
  const [testMode, setTestMode] = useState(true);
  const [baseline, setBaseline] = useState<BaselineLink[] | null>(null);
  const [baselineJunctions, setBaselineJunctions] = useState<{ nodeId: string; delaySec: number }[] | null>(null);
  const [scanRows, setScanRows] = useState<ScanRow[] | null>(null);
  const [scanLoading, setScanLoading] = useState(false);

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

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // ------------------------------------------------------------ network + data status
  useEffect(() => {
    setError(null);
    api.corridor()
      .then((d) => {
        setData(d);
        if (d.dataStatus.ready) setTestMode(false);
      })
      .catch((e: Error) => setError(e.message));
    api.calibration().then(setCalibration).catch(() => setCalibration(null));
  }, [reload]);

  const ready = !!data?.dataStatus.ready;
  const useTest = testMode && !ready;

  // current traffic (coloured map + intersection markers) and the street-by-street check
  useEffect(() => {
    if (!data) return;
    setBaseline(null);
    setBaselineJunctions(null);
    setScanRows(null);
    if (!ready && !useTest) return;
    api.baseline(useTest).then((b) => {
      if (b.status === "ok") {
        setBaseline(b.links);
        setBaselineJunctions(b.junctions);
      }
    }).catch(() => undefined);
    setScanLoading(true);
    api.scan(useTest).then((s) => setScanRows(s.status === "ok" ? s.rows : null)).catch(() => undefined)
      .finally(() => setScanLoading(false));
  }, [data, ready, useTest]);

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
    setStreet(s);
    setHeading(h);
    setPinned(null);
    if (s && h) setPins((ps) => (ps.some((p) => p.street === s && p.heading === h) ? ps : [...ps, { street: s, heading: h }]));
  }, []);

  useEffect(() => {
    const p = pendingScan.current;
    if (p && p.street === street && p.heading === heading) {
      pendingScan.current = null;
      if (p.mode === "closure") setLanes(originalLanes.map(() => "bike"));
      else setLanes(originalLanes.map((l, i) => (i === originalLanes.length - 1 ? "bike" : l)));
      return;
    }
    setLanes(originalLanes);
  }, [originalLanes, street, heading]);

  const pickScan = useCallback((r: ScanRow) => {
    pendingScan.current = r;
    select(r.street, r.heading);
  }, [select]);

  // ------------------------------------------------------------ lanes → changes → live simulation
  const changes: Change[] = useMemo(() => {
    const carAfter = lanes.filter((l) => l === "car").length;
    const removed = maxLanes - carAfter;
    if (removed <= 0) return [];
    const use: LaneUse = lanes.includes("bus") ? "bus" : lanes.includes("bike") ? "bike" : "sidewalk";
    return selectedIds
      .map((id) => {
        const n = linkProps.get(id)?.properties.carLanes ?? 0;
        const after = Math.max(0, n - removed);
        return { linkId: id, carLanesAfter: after, use: (after === 0 ? "closed" : use) as LaneUse };
      })
      .filter((c) => c.carLanesAfter < (linkProps.get(c.linkId)?.properties.carLanes ?? 0));
  }, [lanes, maxLanes, selectedIds, linkProps]);
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
      api.simulate(changes, useTest, c.signal)
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
  }, [changesKey, useTest]);

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
    for (const id of selectedIds) {
      const r = res.get(id);
      const b = base.get(id);
      time += r ? r.timeAfterSec : b ? b.timeSec : 0;
      free += r ? r.freeTimeSec : b ? b.freeTimeSec : 0;
    }
    return free > 0 ? time / free : 1;
  }, [ok, baseline, selectedIds]);

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

  return (
    <I18nContext.Provider value={i18n}>
      <div className="relative h-screen w-screen overflow-hidden bg-[#F8FAFC] text-[#0F172A]">
        {data && (
          <CorridorMap data={data} baseline={baseline} baselineJunctions={baselineJunctions} result={ok} scanRows={scanRows}
            layers={layers} showDelta={showDelta} testData={useTest && !!baseline} selectedLinkIds={selectedIds} pins={mapPins}
            highlight={hovered ?? pinned} focusKey={focusKey} highlightBus={hoverBus} onPickLink={pickLink} />
        )}

        {/* floating glass sidebar */}
        <aside className="glass pointer-events-auto absolute bottom-3 left-3 top-3 z-10 flex w-[410px] max-w-[calc(100vw-24px)] flex-col overflow-hidden rounded-2xl animate-slideIn">
          <header className="flex items-center gap-2.5 border-b border-slate-200/80 px-4 py-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-[15px] font-bold leading-tight tracking-tight">{t.appName}</h1>
            </div>
            <button onClick={() => setExplainer(true)} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#005BBC]" title={t.explain} aria-label={t.explain}>
              <HelpCircle size={17} />
            </button>
            <div className="flex rounded-lg bg-slate-100 p-0.5 font-mono text-[11px]" role="radiogroup" aria-label={t.language}>
              {(["ro", "en"] as const).map((l) => (
                <button key={l} role="radio" aria-checked={lang === l} onClick={() => setLang(l)}
                  className={`rounded-md px-2 py-1 font-semibold uppercase transition ${lang === l ? "bg-white text-[#005BBC] shadow-sm" : "text-slate-500 hover:text-slate-800"}`}>
                  {l}
                </button>
              ))}
            </div>
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
                <DataStatusCard data={data} testMode={testMode} onTestMode={setTestMode} />
                <StreetSearch data={data} street={street} heading={heading} onChange={select} />
                {selectedIds.length > 0 && (
                  <LaneMixer lanes={lanes} original={originalLanes} existingBusLane={existingBusLane} segments={selectedIds.length}
                    lanesSource={lanesSource} slowness={slowness} busy={busy} onChange={setLanes} />
                )}
                <PinsPanel times={pinTimes} onRemove={(p) => setPins((ps) => ps.filter((x) => pinKey(x) !== pinKey(p)))} />
                <ResultsPanel result={result} changes={changes} testData={useTest} onHoverBus={setHoverBus}
                  onHighlight={setHovered} onFocus={(h) => { setPinned(h); setFocusKey((k) => k + 1); }} />
                {(scanRows || scanLoading) && <ScanCard rows={scanRows} loading={scanLoading} onPick={pickScan} />}
                <ModelCheckCard data={data} calibration={calibration} />
              </>
            )}
          </div>
        </aside>

        <div className="pointer-events-none absolute bottom-3 left-[436px] z-10 hidden md:block">
          <LayersPill layers={layers} onChange={setLayers} showDelta={showDelta} onShowDelta={setShowDelta} hasResult={!!ok} />
        </div>

        <BraessToast changePct={toastPct} testData={useTest} onClose={() => setToastPct(null)} />
      </div>
      <CitizenBraessExplainerModal open={explainer} onClose={() => setExplainer(false)} />
    </I18nContext.Provider>
  );
}
