import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, Layers } from "lucide-react";
import type { MapLayers } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  layers: MapLayers;
  onChange: (l: MapLayers) => void;
  showDelta: boolean;
  onShowDelta: (v: boolean) => void;
  hasResult: boolean;
}

function Check({ on, set, label, children }: { on: boolean; set: (v: boolean) => void; label: string; children?: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 text-[12.5px] text-slate-700 hover:bg-slate-100">
      <input type="checkbox" className="h-3.5 w-3.5 accent-[#005BBC]" checked={on} onChange={(e) => set(e.target.checked)} />
      <span className="flex-1">{label}</span>
      {children}
    </label>
  );
}

/** Floating layer & legend pill (bottom-left of the map). */
export default function LayersPill({ layers, onChange, showDelta, onShowDelta, hasResult }: Props) {
  const { t } = useI18n();
  const [open, setOpen] = useState(window.innerHeight > 760);
  const set = (k: keyof MapLayers) => (v: boolean) => onChange({ ...layers, [k]: v });
  const delta = showDelta && hasResult;

  return (
    <section className="glass pointer-events-auto w-[268px] rounded-2xl p-3" aria-label={t.layers}>
      <button className="flex w-full items-center gap-2 text-left text-[13px] font-semibold text-slate-900" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Layers size={15} className="text-[#005BBC]" />
        <span className="flex-1">{t.layers}</span>
        {open ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          <Check on={layers.traffic} set={set("traffic")} label={t.layerTraffic} />
          {layers.traffic && (
            <div className="ml-6 mr-1">
              <div className="h-2 rounded-full" style={{ background: delta
                ? "linear-gradient(90deg,#1d4ed8,#60a5fa,#cbd5e1,#fb923c,#c2410c)"
                : "linear-gradient(90deg,#10b981,#eab308,#ef4444,#7f1d1d)" }} />
              <div className="mt-0.5 flex justify-between font-secondary text-[10.5px] text-slate-500">
                <span>{delta ? t.legendLess : t.legendFast}</span>
                <span>{delta ? t.legendMore : t.legendSlow}</span>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-0.5 text-[11px]" role="radiogroup">
                {[false, true].map((d) => (
                  <button key={String(d)} role="radio" aria-checked={showDelta === d} disabled={d && !hasResult} onClick={() => onShowDelta(d)}
                    className={`rounded-md px-1.5 py-1 font-medium transition disabled:opacity-40 ${showDelta === d ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}>
                    {d ? t.colorDelta : t.colorAbsolute}
                  </button>
                ))}
              </div>
              <Check on={layers.flow} set={set("flow")} label={t.layerFlow} />
            </div>
          )}
          <Check on={layers.glow} set={set("glow")} label={t.layerGlow}>
            <span className="h-2.5 w-4 rounded-full bg-[#d946ef]" />
          </Check>
          <p className="ml-6 text-[10.5px] leading-tight text-slate-500">{t.layerGlowHint}</p>
          <Check on={layers.intersections} set={set("intersections")} label={t.layerIntersections}>
            <span className="h-2.5 w-2.5 rounded-full bg-[#DC2626]" />
          </Check>
          <Check on={layers.gates} set={set("gates")} label={t.layerGates}>
            <span className="flex gap-0.5"><span className="h-2.5 w-2.5 rounded-full bg-[#059669]" /><span className="h-2.5 w-2.5 rounded-full bg-[#DC2626]" /></span>
          </Check>
          <Check on={layers.buildings3d} set={set("buildings3d")} label={t.layer3d} />
        </div>
      )}
    </section>
  );
}
