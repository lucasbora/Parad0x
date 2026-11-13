import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, FileText, Loader2, MousePointerClick, RefreshCw, RotateCcw } from "lucide-react";
import { api } from "./api/client";
import { I18nContext, translations, type Lang } from "./i18n/translations";
import type {
  ColorMode,
  HealthResponse,
  HighlightedRoute,
  Hotspot,
  Intervention,
  LaneType,
  LayerState,
  NetworkResponse,
  Preset,
  RoadProps,
  SimulateRequest,
  SimulateResponse,
  StreetSearchResult,
} from "./types/simulator";
import { fmt, sameLanes } from "./lib/format";
import TrafficMapCanvas, { type FlyTarget } from "./components/map/TrafficMapCanvas";
import LayerToggles from "./components/map/LayerToggles";
import RouteOverlayLegend from "./components/map/RouteOverlayLegend";
import TopNavbar from "./components/studio/TopNavbar";
import HotspotPresetBar from "./components/studio/HotspotPresetBar";
import StreetCrossSectionMixer from "./components/studio/StreetCrossSectionMixer";
import TelemetryCards from "./components/studio/TelemetryCards";
import RecommendedRoutesTabs from "./components/studio/RecommendedRoutesTabs";
import CitizenBraessExplainerModal from "./components/studio/CitizenBraessExplainerModal";
import DecidemExportModal from "./components/studio/DecidemExportModal";
import DataProvenanceBadge from "./components/studio/DataProvenanceBadge";

interface Draft {
  lanes: LaneType[];
  filter: boolean;
}

const DEFAULT_LAYERS: LayerState = {
  traffic: true,
  braess: true,
  flowAnimation: true,
  queues: true,
  stpt: false,
  cycling: false,
  timpark: false,
  zones: false,
  sesizari: false,
  pois: false,
  airQuality: false,
};

function readLang(): Lang {
  try {
    const v = window.localStorage.getItem("tmbg.lang");
    return v === "en" ? "en" : "ro";
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

  const [preset, setPreset] = useState<Preset>("morning_rush");
  const [network, setNetwork] = useState<NetworkResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [netLoading, setNetLoading] = useState(true);
  const [netError, setNetError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null);
  const [activeHotspot, setActiveHotspot] = useState<string | null>(null);
  const [sim, setSim] = useState<SimulateResponse | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);
  const [colorMode, setColorMode] = useState<ColorMode>("absolute");
  const [hovered, setHovered] = useState<HighlightedRoute | null>(null);
  const [pinned, setPinned] = useState<HighlightedRoute | null>(null);
  const [focusKey, setFocusKey] = useState(0);
  const [flyTo, setFlyTo] = useState<FlyTarget | null>(null);
  const [explainer, setExplainer] = useState(false);
  const [decidem, setDecidem] = useState(false);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  // ------------------------------------------------------------ network per preset
  useEffect(() => {
    const ctrl = new AbortController();
    setNetLoading(true);
    setNetError(null);
    api
      .network(preset, ctrl.signal)
      .then((n) => setNetwork(n))
      .catch((e: Error) => {
        if (e.name !== "AbortError") setNetError(e.message);
      })
      .finally(() => setNetLoading(false));
    api.health(ctrl.signal).then(setHealth).catch(() => undefined);
    return () => ctrl.abort();
  }, [preset, reloadKey]);

  const roadById = useMemo(() => {
    const m = new Map<string, RoadProps>();
    network?.roads.features.forEach((f) => m.set(f.properties.id, f.properties));
    return m;
  }, [network]);

  // ------------------------------------------------------------ interventions → simulate
  const interventions: Intervention[] = useMemo(
    () =>
      Object.entries(drafts)
        .filter(([id]) => roadById.has(id))
        .map(([id, d]) => ({
          linkId: id,
          codGis: roadById.get(id)?.codGis,
          newLaneAllocation: d.lanes,
          filterCutThroughRoute: d.filter,
        })),
    [drafts, roadById],
  );
  const simRequest: SimulateRequest | null = useMemo(
    () => (interventions.length ? { preset, interventions } : null),
    [preset, interventions],
  );

  const simCtrl = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!network) return;
    simCtrl.current?.abort();
    if (!simRequest) {
      setSim(null);
      setSimulating(false);
      return;
    }
    const ctrl = new AbortController();
    simCtrl.current = ctrl;
    setSimulating(true);
    setSimError(null);
    const id = window.setTimeout(() => {
      api
        .simulate(simRequest, ctrl.signal)
        .then((r) => setSim(r))
        .catch((e: Error) => {
          if (e.name !== "AbortError") setSimError(e.message);
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setSimulating(false);
        });
    }, 90);
    return () => {
      window.clearTimeout(id);
      ctrl.abort();
    };
  }, [simRequest, network]);

  useEffect(() => {
    if (!sim) setColorMode("absolute");
  }, [sim]);

  // ------------------------------------------------------------ handlers
  const selected = selectedLinkId ? roadById.get(selectedLinkId) ?? null : null;
  const draft = selectedLinkId ? drafts[selectedLinkId] : undefined;
  const lanes = draft?.lanes ?? selected?.lanes ?? [];

  const updateDraft = useCallback(
    (linkId: string, patch: Partial<Draft>) => {
      const road = roadById.get(linkId);
      if (!road) return;
      setDrafts((prev) => {
        const cur = prev[linkId] ?? { lanes: road.lanes, filter: false };
        const next = { ...cur, ...patch };
        const copy = { ...prev };
        if (sameLanes(next.lanes, road.lanes) && !next.filter) delete copy[linkId];
        else copy[linkId] = next;
        return copy;
      });
    },
    [roadById],
  );

  const selectLink = useCallback((id: string) => {
    setSelectedLinkId(id);
    setPinned(null);
  }, []);

  const pickHotspot = useCallback((h: Hotspot) => {
    setActiveHotspot(h.id);
    setSelectedLinkId(h.linkId);
    setDrafts({ [h.linkId]: { lanes: h.suggestedLanes, filter: false } });
    setFlyTo({ center: h.center, zoom: h.zoom, key: Date.now() });
    setPinned(null);
    setColorMode("delta");
  }, []);

  const pickStreet = useCallback(
    (r: StreetSearchResult) => {
      if (r.linkId && roadById.has(r.linkId)) {
        setSelectedLinkId(r.linkId);
        if (r.center) setFlyTo({ center: r.center, zoom: 15.6, key: Date.now() });
      }
    },
    [roadById],
  );

  const resetAll = () => {
    setDrafts({});
    setActiveHotspot(null);
    setPinned(null);
  };

  const highlighted = hovered ?? pinned;
  const update = sim && selectedLinkId ? sim.updatedLinks.find((u) => u.id === selectedLinkId) ?? null : null;
  const editedIds = Object.keys(drafts);
  const twin = selected?.twinId && roadById.has(selected.twinId) ? selected.twinId : null;

  return (
    <I18nContext.Provider value={i18n}>
      <div className="relative h-screen w-screen overflow-hidden bg-[#F8FAFC] font-sans text-[#0F172A]">
        <TrafficMapCanvas
          network={network}
          sim={sim}
          layers={layers}
          colorMode={colorMode}
          selectedLinkId={selectedLinkId}
          editedLinkIds={editedIds}
          highlighted={highlighted}
          focusKey={focusKey}
          flyTo={flyTo}
          onSelectLink={selectLink}
        />

        {/* top-left control island */}
        <div className="pointer-events-none absolute left-3 top-3 z-10 flex max-h-[calc(100vh-80px)] w-[340px] max-w-[calc(100vw-24px)] flex-col gap-2 overflow-y-auto">
          <TopNavbar network={network} health={health} onPickStreet={pickStreet} onExplain={() => setExplainer(true)} />
          <HotspotPresetBar
            hotspots={network?.hotspots ?? []}
            preset={preset}
            loading={netLoading}
            activeHotspotId={activeHotspot}
            onPreset={setPreset}
            onHotspot={pickHotspot}
          />
        </div>

        {/* bottom-left layers */}
        <div className="pointer-events-none absolute bottom-3 left-3 z-10 hidden md:block">
          <LayerToggles layers={layers} onChange={setLayers} colorMode={colorMode} onColorMode={setColorMode} hasSimulation={!!sim} defaultOpen={window.innerHeight >= 900} />
        </div>

        {/* bottom-centre legend */}
        <div className="pointer-events-none absolute bottom-3 left-1/2 z-10 hidden -translate-x-1/2 lg:block">
          <RouteOverlayLegend sim={sim} network={network} />
        </div>

        {/* right-hand studio card */}
        <aside
          className="pointer-events-none absolute bottom-3 right-14 top-3 z-10 flex w-[430px] max-w-[calc(100vw-24px)] flex-col"
          aria-label={t.streetCard}
        >
          <div className="pointer-events-auto flex max-h-full flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-50/95 shadow-island backdrop-blur animate-slideIn">
            <div className="flex items-center gap-2 border-b border-slate-200 bg-white/80 px-3 py-2">
              {editedIds.length > 0 ? (
                <>
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-emerald-800">
                    {editedIds.length} {t.interventionsActive}
                  </span>
                  <button onClick={resetAll} className="flex items-center gap-1 text-[11.5px] font-medium text-slate-500 hover:text-slate-900">
                    <RotateCcw size={12} /> {t.resetAll}
                  </button>
                </>
              ) : (
                <span className="text-[11.5px] text-slate-500">
                  {network ? `${t.networkStats}: ${network.stats.roadLinks} links · ${network.stats.queueLinks} queues · ${network.stats.odPairs} OD · ${network.stats.braessCandidates} Braess` : ""}
                </span>
              )}
              <div className="flex-1" />
              {simulating && <Loader2 size={14} className="animate-spin text-slate-400" aria-label={t.simulating} />}
              <button
                onClick={() => setDecidem(true)}
                disabled={!simRequest}
                className="flex items-center gap-1 rounded-lg bg-[#005BBC] px-2.5 py-1 text-[11.5px] font-semibold text-white shadow-sm hover:bg-[#004a99] disabled:opacity-40"
              >
                <FileText size={12} /> {t.decidemExport}
              </button>
            </div>

            <div className="flex-1 space-y-2.5 overflow-y-auto p-2.5">
              {netError && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-[12.5px] text-red-800">
                  <div className="flex items-center gap-2 font-semibold"><AlertTriangle size={15} /> {t.backendDown}</div>
                  <p className="mt-1 font-mono text-[11px]">{netError}</p>
                  <button onClick={() => setReloadKey((k) => k + 1)} className="mt-2 flex items-center gap-1 rounded-lg bg-white px-2 py-1 text-[12px] font-medium shadow-sm">
                    <RefreshCw size={12} /> {t.retry}
                  </button>
                </div>
              )}
              {!network && !netError && (
                <div className="flex items-center gap-2 p-3 text-[12.5px] text-slate-500"><Loader2 size={15} className="animate-spin" /> {t.loadingNetwork}</div>
              )}

              {selected ? (
                <StreetCrossSectionMixer
                  key={selected.id}
                  link={selected}
                  lanes={lanes}
                  filterCutThrough={draft?.filter ?? false}
                  update={update}
                  simulating={simulating}
                  onLanes={(l) => updateDraft(selected.id, { lanes: l })}
                  onFilter={(v) => updateDraft(selected.id, { filter: v })}
                  onSwitchDirection={twin ? () => setSelectedLinkId(twin) : null}
                  onClose={() => setSelectedLinkId(null)}
                />
              ) : (
                network && (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4">
                    <div className="flex items-center gap-2 text-[14px] font-semibold text-slate-900">
                      <MousePointerClick size={16} className="text-[#005BBC]" /> {t.emptyStateTitle}
                    </div>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-slate-600">{t.emptyStateBody}</p>
                  </div>
                )
              )}

              {simError && <p className="rounded-lg bg-red-50 p-2 font-mono text-[11px] text-red-700">{simError}</p>}

              {network && <TelemetryCards baseline={network.baselineMetrics} simulated={sim?.simulatedMetrics ?? null} network={network} />}

              {sim && (
                <RecommendedRoutesTabs
                  sim={sim}
                  onHover={setHovered}
                  onFocus={(r) => {
                    setPinned(r);
                    setFocusKey((k) => k + 1);
                  }}
                  onExplain={() => setExplainer(true)}
                />
              )}

              {network && (
                <details className="rounded-xl border border-slate-200 bg-white p-2.5 text-[11px]">
                  <summary className="cursor-pointer font-semibold text-slate-700">{t.provenance}</summary>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {network.provenance.map((p) => (
                      <DataProvenanceBadge
                        key={p.dataset}
                        label={`${p.dataset} · ${p.source}${p.fetchedAt ? ` · ${p.fetchedAt.slice(0, 10)}` : ""}`}
                        tone={p.source === "seed" ? "seed" : "live"}
                        title={`${p.endpoint}${p.note ? ` — ${p.note}` : ""}`}
                      />
                    ))}
                    <DataProvenanceBadge
                      label={`FIWARE ${network.fiwareSensor.name} · ${fmt(network.fiwareSensor.intensity_veh_h_peak, 0)} veh/h · ${network.fiwareSensor.dateObserved}`}
                    />
                  </div>
                  <p className="mt-2 text-slate-500">{t.owners}</p>
                </details>
              )}
            </div>
          </div>
        </aside>

        <CitizenBraessExplainerModal open={explainer} onClose={() => setExplainer(false)} />
        <DecidemExportModal open={decidem} request={simRequest} onClose={() => setDecidem(false)} />
      </div>
    </I18nContext.Provider>
  );
}
