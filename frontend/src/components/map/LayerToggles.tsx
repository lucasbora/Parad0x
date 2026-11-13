import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, Layers } from "lucide-react";
import type { ColorMode, LayerState } from "../../types/simulator";
import { useI18n } from "../../i18n/translations";

interface Props {
  layers: LayerState;
  onChange: (next: LayerState) => void;
  colorMode: ColorMode;
  onColorMode: (m: ColorMode) => void;
  hasSimulation: boolean;
  defaultOpen?: boolean;
}

function Check({ checked, onChange, label, children }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  children?: ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 text-[12.5px] text-slate-700 hover:bg-slate-100">
      <input
        type="checkbox"
        className="h-3.5 w-3.5 rounded border-slate-300 accent-[#005BBC] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#005BBC]"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="flex-1">{label}</span>
      {children}
    </label>
  );
}

/** Floating bottom-left layer & legend pill (Leon Zhao style). */
export default function LayerToggles({ layers, onChange, colorMode, onColorMode, hasSimulation, defaultOpen = true }: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(defaultOpen);
  const [greenOpen, setGreenOpen] = useState(false);
  const set = (k: keyof LayerState) => (v: boolean) => onChange({ ...layers, [k]: v });

  return (
    <section
      aria-label={t.layers}
      className="pointer-events-auto w-[272px] rounded-2xl border border-slate-200/80 bg-white/95 p-3 shadow-island backdrop-blur"
    >
      <button
        className="flex w-full items-center gap-2 text-left text-[13px] font-semibold text-slate-900"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <Layers size={15} className="text-[#005BBC]" aria-hidden />
        <span className="flex-1">{t.layers}</span>
        {open ? <ChevronDown size={15} aria-hidden /> : <ChevronUp size={15} aria-hidden />}
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          <Check checked={layers.traffic} onChange={set("traffic")} label={t.simulatedTraffic} />
          {layers.traffic && (
            <div className="ml-6 mr-1">
              {colorMode === "absolute" || !hasSimulation ? (
                <>
                  <div className="h-2 rounded-full" style={{ background: "linear-gradient(90deg,#10b981,#3b82f6,#f59e0b,#ef4444)" }} />
                  <div className="mt-0.5 flex justify-between font-mono text-[10.5px] text-slate-500">
                    <span>{t.fast}</span>
                    <span>{t.slow}</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="h-2 rounded-full" style={{ background: "linear-gradient(90deg,#1d4ed8,#10b981,#cbd5e1,#fb923c,#c2410c)" }} />
                  <div className="mt-0.5 flex justify-between font-mono text-[10.5px] text-slate-500">
                    <span>{t.deltaLess}</span>
                    <span>{t.deltaMore}</span>
                  </div>
                </>
              )}
              <div className="mt-1.5 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-0.5 text-[11px]" role="radiogroup">
                {(["absolute", "delta"] as ColorMode[]).map((m) => (
                  <button
                    key={m}
                    role="radio"
                    aria-checked={colorMode === m}
                    disabled={m === "delta" && !hasSimulation}
                    onClick={() => onColorMode(m)}
                    className={`rounded-md px-1.5 py-1 font-medium transition disabled:opacity-40 ${
                      colorMode === m ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    {m === "absolute" ? t.colorAbsolute : t.colorDelta}
                  </button>
                ))}
              </div>
              <Check checked={layers.flowAnimation} onChange={set("flowAnimation")} label={t.flowAnimation} />
            </div>
          )}
          <Check checked={layers.braess} onChange={set("braess")} label={t.braessRoad}>
            <span className="h-2.5 w-7 rounded-full shadow-[0_0_8px_2px_rgba(16,185,129,0.65)] ring-1 ring-fuchsia-500" style={{ background: "#10b981" }} />
          </Check>
          <p className="ml-6 text-[10.5px] leading-tight text-slate-500">{t.braessRoadHint}</p>
          <Check checked={layers.queues} onChange={set("queues")} label={t.layerQueues}>
            <span className="h-2.5 w-2.5 rounded-full bg-[#DC2626]" />
          </Check>

          <button
            className="mt-1 flex w-full items-center gap-1 border-t border-slate-100 pt-2 text-left text-[12px] font-semibold text-slate-700"
            onClick={() => setGreenOpen((o) => !o)}
            aria-expanded={greenOpen}
          >
            <span className="flex-1">{t.greenOverlays}</span>
            {greenOpen ? <ChevronUp size={14} aria-hidden /> : <ChevronDown size={14} aria-hidden />}
          </button>
          {greenOpen && (
            <div className="space-y-0.5">
              <Check checked={layers.stpt} onChange={set("stpt")} label={t.layerStpt}>
                <span className="h-1 w-6 rounded bg-[#6f2095]" />
              </Check>
              <Check checked={layers.cycling} onChange={set("cycling")} label={t.layerCycling}>
                <span className="h-0 w-6 border-t-2 border-dotted border-[#059669]" />
              </Check>
              <Check checked={layers.timpark} onChange={set("timpark")} label={t.layerTimpark}>
                <span className="flex gap-0.5">
                  {["#16a34a", "#dc2626", "#eab308", "#2563eb"].map((c) => (
                    <span key={c} className="h-2 w-1.5 rounded-sm" style={{ background: c }} />
                  ))}
                </span>
              </Check>
              <Check checked={layers.zones} onChange={set("zones")} label={t.layerZones} />
              <Check checked={layers.sesizari} onChange={set("sesizari")} label={t.layerSesizari}>
                <span className="h-2.5 w-2.5 rounded-full border border-[#D97706] bg-amber-200" />
              </Check>
              <Check checked={layers.pois} onChange={set("pois")} label={t.layerPois}>
                <span className="h-2.5 w-2.5 rounded-full bg-[#005BBC]" />
              </Check>
              <Check checked={layers.airQuality} onChange={set("airQuality")} label={t.layerAir} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
