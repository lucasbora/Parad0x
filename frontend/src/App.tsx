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
  LaneKind,
  LaneUse,
  LngLat,
  Pin,
  SimulateResponse,
} from "./types/corridor";
import CorridorMap, { type MapPinView } from "./components/CorridorMap";
import DataStatusCard from "./components/DataStatusCard";
import StreetSearch from "./components/StreetSearch";
import LaneMixer from "./components/LaneMixer";
import PinsPanel, { type PinTime } from "./components/PinsPanel";
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

  const [street, setStreet] = useState<string | null>(null);
  const [heading, setHeading] = useState<string | null>(null);
  const [lanes, setLanes] = useState<LaneKind[]>([]);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [pins, setPins] = useState<Pin[]>([]);
  const [showDelta, setShowDelta] = useState(false);
  const [hoverBus, setHoverBus] = useState<BusResult | null>(null);
  const [toastPct, setToastPct] = useState<number | null>(null);
  const [explainer, setExplainer] = useState(false);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // ------------------------------------------------------------ load network + data status
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

  // current-state traffic for the coloured map
  useEffect(() => {
    if (!data) return;
    if (!ready && !useTest) {
      setBaseline(null);
      return;
    }
    api.baseline(useTest).then((b) => setBaseline(b.status === "ok" ? b.links : null)).catch(() => setBaseline(null));
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
    if (s && h) setPins((ps) => (ps.some((p) => p.street === s && p.heading === h) ? ps : [...ps, { street: s, heading: h }]));
  }, []);

  useEffect(() => {
    setLanes(originalLanes);
  }, [originalLanes, street, heading]);

  // ------------------------------------------------------------ lanes → backend changes
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

  // run the simulation automatically after every lane change
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
    if (!ok) setShowDelta(false);
  }, [ok]);

  // ------------------------------------------------------------ pins: travel time per street direction
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
      const before = ok ? sum((id) => res.get(id)?.timeBeforeSec) : sum((id) => base.get(id));
      const after = ok ? sum((id) => res.get(id)?.timeAfterSec) : null;
      return { pin, beforeSec: before, afterSec: after };
    });
  }, [pins, data, baseline, ok]);

  const mapPins: MapPinView[] = useMemo(() => {
    return pinTimes.map(({ pin, beforeSec, afterSec }) => {
      const ids = data?.streets.find((s) => s.street === pin.street)?.directions.find((d) => d.heading === pin.heading)?.linkIds ?? [];
      const longest = ids
        .map((id) => linkProps.get(id))
        .filter((f): f is NonNullable<typeof f> => !!f)
        .sort((a, b) => b.properties.lengthM - a.properties.lengthM)[0];
      const g = longest?.geometry.coordinates ?? [];
      const at: LngLat = g.length ? g[Math.floor(g.length / 2)] : [0, 0];
      return { key: pinKey(pin), label: `${pin.street} · ${t.heading[pin.heading] ?? pin.heading}`, at, beforeSec, afterSec };
    });
  }, [pinTimes, data, linkProps, t]);

  const pickLink = useCallback(
    (id: string) => {
      const f = linkProps.get(id);
      if (!f || !data) return;
      const p = f.properties;
      const s = data.streets.find((x) => x.street === p.street);
      if (s && s.directions.some((d) => d.heading === p.heading)) select(p.street, p.heading);
    },
    [linkProps, data, select],
  );

  return (
    <I18nContext.Provider value={i18n}>
      <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#F8FAFC] text-[#0F172A] md:flex-row">
        <aside className="flex max-h-[55vh] w-full shrink-0 flex-col border-b border-slate-200 bg-white md:h-full md:max-h-none md:w-[410px] md:border-b-0 md:border-r">
          <header className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-[16px] font-bold leading-tight">{t.appName}</h1>
              <p className="truncate text-[12px] text-slate-500">{data ? `${data.corridor.name} · ${t.peak} ${data.corridor.peak}` : t.subtitle}</p>
            </div>
            <button onClick={() => setExplainer(true)} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100" title={t.explain} aria-label={t.explain}>
              <HelpCircle size={17} />
            </button>
            <div className="flex rounded-lg bg-slate-100 p-0.5 font-mono text-[11px]" role="radiogroup" aria-label={t.language}>
              {(["ro", "en"] as const).map((l) => (
                <button key={l} role="radio" aria-checked={lang === l} onClick={() => setLang(l)}
                  className={`rounded-md px-2 py-1 font-semibold uppercase ${lang === l ? "bg-white text-[#005BBC] shadow-sm" : "text-slate-500"}`}>
                  {l}
                </button>
              ))}
            </div>
          </header>

          <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-[12.5px] text-red-800">
                {t.backendDown}
                <p className="mt-1 font-mono text-[11px]">{error}</p>
                <button onClick={() => setReload((r) => r + 1)} className="mt-2 flex items-center gap-1 rounded bg-white px-2 py-1 text-[12px] shadow-sm">
                  <RefreshCw size={12} /> {t.retry}
                </button>
              </div>
            )}
            {!data && !error && (
              <p className="flex items-center gap-2 text-[13px] text-slate-500"><Loader2 size={15} className="animate-spin" /> {t.loading}</p>
            )}
            {data && (
              <>
                <DataStatusCard data={data} testMode={testMode} onTestMode={setTestMode} />
                <StreetSearch data={data} street={street} heading={heading} onChange={select} />
                {selectedIds.length > 0 && (
                  <LaneMixer lanes={lanes} original={originalLanes} existingBusLane={existingBusLane} segments={selectedIds.length}
                    lanesSource={lanesSource} busy={busy} onChange={setLanes} />
                )}
                <PinsPanel times={pinTimes} onRemove={(p) => setPins((ps) => ps.filter((x) => pinKey(x) !== pinKey(p)))} />
                {ok && (
                  <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-slate-700">
                    <input type="checkbox" className="h-4 w-4 accent-[#005BBC]" checked={showDelta} onChange={(e) => setShowDelta(e.target.checked)} />
                    {t.showDelta}
                  </label>
                )}
                <ResultsPanel result={result} changes={changes} testData={useTest} onHoverBus={setHoverBus} />
                <ModelCheckCard data={data} calibration={calibration} />
              </>
            )}
          </div>
        </aside>

        <main className="relative min-h-[320px] flex-1">
          {data && (
            <CorridorMap data={data} baseline={baseline} result={ok} showDelta={showDelta} testData={useTest && !!baseline}
              selectedLinkIds={selectedIds} pins={mapPins} highlightBus={hoverBus} onPickLink={pickLink} />
          )}
          <BraessToast changePct={toastPct} testData={useTest} onClose={() => setToastPct(null)} />
        </main>
      </div>
      <CitizenBraessExplainerModal open={explainer} onClose={() => setExplainer(false)} />
    </I18nContext.Provider>
  );
}
