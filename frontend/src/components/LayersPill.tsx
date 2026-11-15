import { useState, type ReactNode } from "react";
import { ChevronUp, Layers } from "lucide-react";
import type { MapLayers } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { useSlidingThumb } from "../motion";
import Collapse from "./Collapse";

interface Props {
  layers: MapLayers;
  onChange: (l: MapLayers) => void;
  showDelta: boolean;
  onShowDelta: (v: boolean) => void;
  hasResult: boolean;
}

const ABSOLUTE = "linear-gradient(90deg,#10b981,#eab308,#ef4444,#7f1d1d)";
const DELTA = "linear-gradient(90deg,#1d4ed8,#60a5fa,#cbd5e1,#fb923c,#c2410c)";

function Check({ on, set, label, children, className = "" }: { on: boolean; set: (v: boolean) => void; label: string; children?: ReactNode; className?: string }) {
  return (
    <label className={`flex cursor-pointer items-center gap-2 rounded-md px-1 py-0.5 text-[12.5px] text-slate-700 transition-colors hover:bg-slate-100 ${className}`}>
      <input type="checkbox" className="h-3.5 w-3.5 accent-[#005BBC]" checked={on} onChange={(e) => set(e.target.checked)} />
      <span className="flex-1">{label}</span>
      {children}
    </label>
  );
}

/** Floating layer & legend pill (bottom-left of the map). */
export default function LayersPill({ layers, onChange, showDelta, onShowDelta, hasResult }: Props) {
  const { t } = useI18n();
  // starts open only where there is room for it (tall enough, not a phone)
  const [open, setOpen] = useState(window.innerHeight > 760 && window.innerWidth >= 768);
  const set = (k: keyof MapLayers) => (v: boolean) => onChange({ ...layers, [k]: v });
  const delta = showDelta && hasResult;
  const thumb = useSlidingThumb(String(showDelta));

  return (
    <section className="glass pointer-events-auto w-[268px] rounded-2xl p-3" aria-label={t.layers}>
      <button className="flex w-full items-center gap-2 text-left text-[13px] font-semibold text-slate-900" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Layers size={15} className="text-[#005BBC]" />
        <span className="flex-1">{t.layers}</span>
        <ChevronUp size={15} className={`transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${open ? "rotate-180" : ""}`} />
      </button>
      <Collapse open={open}>
        <div className="mt-2 space-y-1.5">
          <Check on={layers.traffic} set={set("traffic")} label={t.layerTraffic} />
          <Collapse open={layers.traffic}>
            <div className="ml-6 mr-1">
              {/* the two legends cross-fade when switching between absolute and before/after colours */}
              <div className="relative h-2 overflow-hidden rounded-full">
                <div className="absolute inset-0 transition-opacity duration-500" style={{ background: ABSOLUTE, opacity: delta ? 0 : 1 }} />
                <div className="absolute inset-0 transition-opacity duration-500" style={{ background: DELTA, opacity: delta ? 1 : 0 }} />
              </div>
              <div key={String(delta)} className="m-fade-in mt-0.5 flex justify-between font-secondary text-[10.5px] text-slate-500">
                <span>{delta ? t.legendLess : t.legendFast}</span>
                <span>{delta ? t.legendMore : t.legendSlow}</span>
              </div>
              <div ref={thumb.ref} className="relative mt-1.5 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-0.5 text-[11px]" role="radiogroup">
                <span aria-hidden="true" style={thumb.style}
                  className="absolute left-0 top-0 rounded-md bg-white shadow-sm transition-[transform,width,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]" />
                {[false, true].map((d) => (
                  <button key={String(d)} role="radio" data-thumb-key={String(d)} aria-checked={showDelta === d} disabled={d && !hasResult} onClick={() => onShowDelta(d)}
                    className={`relative rounded-md px-1.5 py-1 font-medium transition-colors duration-300 disabled:opacity-40 ${showDelta === d ? "text-slate-900" : "text-slate-500 hover:text-slate-800"}`}>
                    {d ? t.colorDelta : t.colorAbsolute}
                  </button>
                ))}
              </div>
              <Check on={layers.flow} set={set("flow")} label={t.layerFlow} className="mt-1.5" />
            </div>
          </Collapse>
          <Check on={layers.glow} set={set("glow")} label={t.layerGlow}>
            {/* two thin parallel lines, like the outline drawn around Braess streets on the map */}
            <span className="flex h-2.5 w-5 flex-col justify-between" aria-hidden="true">
              <span className="h-[2px] rounded-full bg-[#d946ef]" />
              <span className="h-[2px] rounded-full bg-[#d946ef]" />
            </span>
          </Check>
          {/* map markers: white ring + slight shadow, as drawn on the map */}
          <Check on={layers.intersections} set={set("intersections")} label={t.layerIntersections}>
            <span className="flex gap-0.5" aria-hidden="true">
              <span className="h-3 w-3 rounded-full border-2 border-white bg-[#059669] shadow-[0_1px_2px_rgba(15,23,42,0.35)]" />
              <span className="h-3 w-3 rounded-full border-2 border-white bg-[#dc2626] shadow-[0_1px_2px_rgba(15,23,42,0.35)]" />
            </span>
          </Check>
          <Check on={layers.gates} set={set("gates")} label={t.layerGates}>
            {/* a short bar across the road, as drawn on the map */}
            <span className="h-3.5 w-[7px] rounded-full border-[1.5px] border-white bg-black shadow-[0_1px_2px_rgba(15,23,42,0.35)]" aria-hidden="true" />
          </Check>
        </div>
      </Collapse>
    </section>
  );
}
