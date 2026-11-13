import { useCallback, useEffect, useMemo, useState } from "react";
import { HelpCircle, Loader2, RefreshCw } from "lucide-react";
import { api } from "./api";
import { I18nContext, translations, type Lang } from "./i18n/translations";
import type { BusResult, CalibrationResponse, Change, CorridorResponse, LaneUse, SimulateResponse } from "./types/corridor";
import CorridorMap from "./components/CorridorMap";
import DataStatusCard from "./components/DataStatusCard";
import StreetPicker from "./components/StreetPicker";
import LaneEditor from "./components/LaneEditor";
import ResultsPanel from "./components/ResultsPanel";
import ModelCheckCard from "./components/ModelCheckCard";
import CitizenBraessExplainerModal from "./components/CitizenBraessExplainerModal";

function readLang(): Lang {
  try {
    return window.localStorage.getItem("tmbg.lang") === "en" ? "en" : "ro";
  } catch {
    return "ro";
  }
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
  const [street, setStreet] = useState<string | null>(null);
  const [heading, setHeading] = useState<string | null>(null);
  const [lanesAfter, setLanesAfter] = useState(0);
  const [use, setUse] = useState<LaneUse>("bus");
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [hoverBus, setHoverBus] = useState<BusResult | null>(null);
  const [explainer, setExplainer] = useState(false);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    setError(null);
    api.corridor().then(setData).catch((e: Error) => setError(e.message));
    api.calibration().then(setCalibration).catch(() => setCalibration(null));
  }, [reload]);

  const linkProps = useMemo(() => new Map((data?.links.features ?? []).map((f) => [f.properties.id, f.properties])), [data]);
  const selectedIds = useMemo(() => {
    const s = data?.streets.find((x) => x.street === street);
    return s?.directions.find((d) => d.heading === heading)?.linkIds ?? [];
  }, [data, street, heading]);
  const maxLanes = Math.max(0, ...selectedIds.map((id) => linkProps.get(id)?.carLanes ?? 0));

  const select = useCallback(
    (s: string | null, h: string | null) => {
      setStreet(s);
      setHeading(h);
      setResult(null);
    },
    [],
  );

  useEffect(() => {
    setLanesAfter(Math.max(0, maxLanes - 1));
  }, [maxLanes, street, heading]);

  const changes: Change[] = useMemo(() => {
    const removed = maxLanes - lanesAfter;
    if (removed <= 0) return [];
    return selectedIds
      .map((id) => {
        const lanes = linkProps.get(id)?.carLanes ?? 0;
        const after = Math.max(0, lanes - removed);
        return { linkId: id, carLanesAfter: after, use: (after === 0 ? "closed" : use) as LaneUse };
      })
      .filter((c) => c.carLanesAfter < (linkProps.get(c.linkId)?.carLanes ?? 0));
  }, [selectedIds, linkProps, maxLanes, lanesAfter, use]);

  const run = async () => {
    if (!changes.length) return;
    setRunning(true);
    try {
      setResult(await api.simulate(changes));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const pickLink = useCallback(
    (id: string) => {
      const p = linkProps.get(id);
      if (!p || !data) return;
      const s = data.streets.find((x) => x.street === p.street);
      if (s && s.directions.some((d) => d.heading === p.heading)) select(p.street, p.heading);
    },
    [linkProps, data, select],
  );

  const ok = result && result.status === "ok" ? result : null;

  return (
    <I18nContext.Provider value={i18n}>
      <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#F8FAFC] text-[#0F172A] md:flex-row">
        <aside className="flex w-full shrink-0 flex-col border-b border-slate-200 bg-white md:h-full md:w-[400px] md:border-b-0 md:border-r">
          <header className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-[16px] font-bold leading-tight text-[#0F172A]">{t.appName}</h1>
              <p className="truncate text-[12px] text-slate-500">
                {data ? `${data.corridor.name} · ${t.peak} ${data.corridor.peak}` : t.subtitle}
              </p>
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
                <DataStatusCard data={data} />
                <StreetPicker data={data} street={street} heading={heading} onChange={select} />
                {selectedIds.length > 0 && (
                  <LaneEditor maxLanes={maxLanes} lanesAfter={lanesAfter} use={use} running={running} disabled={!changes.length}
                    onLanesAfter={(n) => { setLanesAfter(n); setResult(null); }}
                    onUse={(u) => { setUse(u); setResult(null); }} onRun={run} />
                )}
                <ResultsPanel result={result} changes={changes} onHoverBus={setHoverBus} />
                <ModelCheckCard data={data} calibration={calibration} />
              </>
            )}
          </div>
        </aside>

        <main className="relative min-h-[320px] flex-1">
          {data && <CorridorMap data={data} result={ok} selectedLinkIds={selectedIds} highlightBus={hoverBus} onPickLink={pickLink} />}
        </main>
      </div>
      <CitizenBraessExplainerModal open={explainer} onClose={() => setExplainer(false)} />
    </I18nContext.Provider>
  );
}
