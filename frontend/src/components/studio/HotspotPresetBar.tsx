import { CalendarClock, Flame, Loader2, Moon, Sun, Sunrise, Trees , type LucideIcon } from "lucide-react";
import { useI18n } from "../../i18n/translations";
import type { Hotspot, Preset } from "../../types/simulator";
import { signed } from "../../lib/format";

interface Props {
  hotspots: Hotspot[];
  preset: Preset;
  loading: boolean;
  activeHotspotId: string | null;
  onPreset: (p: Preset) => void;
  onHotspot: (h: Hotspot) => void;
}

const PRESET_ICONS: Record<Preset, LucideIcon> = {
  morning_rush: Sunrise,
  evening_rush: Moon,
  now: Sun,
  weekend: Trees,
  event_rush: CalendarClock,
};

const ORDER: Preset[] = ["morning_rush", "evening_rush", "now", "weekend", "event_rush"];

/** "Paradox hotspots" quick-select row + time-of-day demand pills. */
export default function HotspotPresetBar({ hotspots, preset, loading, activeHotspotId, onPreset, onHotspot }: Props) {
  const { t, lang } = useI18n();
  // Busiest / highest-impact first (fixed featured ranking), as in the reference simulator.
  const sorted = [...hotspots].sort((a, b) => a.rank - b.rank);

  return (
    <section className="pointer-events-auto rounded-2xl border border-slate-200/80 bg-white/95 p-3 shadow-island backdrop-blur">
      <div className="flex items-baseline justify-between">
        <h2 className="flex items-center gap-1.5 text-[12.5px] font-semibold text-slate-900">
          <Flame size={14} className="text-[#059669]" aria-hidden /> {t.hotspotsTitle}
        </h2>
        <span className="text-[10.5px] text-slate-400">{t.hotspotsHint}</span>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        {sorted.map((h) => {
          const active = activeHotspotId === h.id;
          const negative = h.braessValueV < 0;
          return (
            <button
              key={h.id}
              onClick={() => onHotspot(h)}
              className={`group flex items-center gap-2 rounded-xl border px-2.5 py-1.5 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#005BBC] ${
                active ? "border-[#059669] bg-emerald-50" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
              }`}
              title={lang === "ro" ? h.storyRo : h.storyEn}
            >
              <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full font-mono text-[10.5px] font-semibold ${
                active ? "bg-[#059669] text-white" : "bg-slate-100 text-slate-600"}`}>
                {h.rank}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12.5px] font-medium text-slate-900">{h.name}</span>
                <span className="block truncate text-[10.5px] text-slate-500">{h.cartier}</span>
              </span>
              <span className={`shrink-0 font-mono text-[11px] font-semibold ${negative ? "text-[#059669]" : "text-slate-500"}`}>
                {signed(h.delayReductionPct, 1)}%
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <h2 className="text-[12.5px] font-semibold text-slate-900">{t.presetTitle}</h2>
        {loading && <Loader2 size={13} className="animate-spin text-slate-400" aria-label="loading" />}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1" role="radiogroup" aria-label={t.presetTitle}>
        {ORDER.map((p) => {
          const Icon = PRESET_ICONS[p];
          const on = p === preset;
          return (
            <button
              key={p}
              role="radio"
              aria-checked={on}
              onClick={() => onPreset(p)}
              title={t.presetHints[p]}
              className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11.5px] font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#005BBC] ${
                on ? "border-[#005BBC] bg-[#005BBC] text-white shadow-sm" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
            >
              <Icon size={12} aria-hidden />
              {t.presets[p]}
            </button>
          );
        })}
      </div>
      <p className="mt-1.5 text-[10.5px] leading-tight text-slate-500">{t.presetHints[preset]}</p>
    </section>
  );
}
