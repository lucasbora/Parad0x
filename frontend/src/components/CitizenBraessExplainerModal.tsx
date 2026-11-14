import { useEffect, useRef, useState } from "react";
import { Car, X } from "lucide-react";
import { useI18n } from "../i18n/translations";

interface Props {
  open: boolean;
  onClose: () => void;
}

/**
 * Textbook Braess diamond (A → D), with small whole numbers so every step can be read off:
 *   A→C and B→D: always FLAT minutes        A→B and C→D: t cars take t minutes each
 *   B→C shortcut: SHORT minutes
 * The explanation texts in translations.ts are written for CARS = 6.
 */
const CARS = 6;
const FLAT = 6;
const SHORT = 1;

interface State {
  up: number;   // cars on A → C → D
  down: number; // cars on A → B → D
  cut: number;  // cars on A → B → C → D
  ab: number;   // cars (= minutes) on the busy road A → B
  cd: number;   // cars (= minutes) on the busy road C → D
  time: number; // trip time of every driver (all used routes take the same time)
}

function equilibrium(shortcut: boolean): State {
  const half = CARS / 2;
  if (!shortcut) return { up: half, down: half, cut: 0, ab: half, cd: half, time: half + FLAT };
  // with the shortcut, a busy road settles at FLAT − SHORT cars, unless that needs more cars than exist
  const busy = Math.min(CARS, Math.max(half, FLAT - SHORT));
  const cut = 2 * busy - CARS;
  const side = CARS - busy;
  return { up: side, down: side, cut, ab: busy, cd: busy, time: cut > 0 ? 2 * busy + SHORT : busy + FLAT };
}

const N = { A: [70, 150], C: [280, 50], B: [280, 250], D: [490, 150] } as const;
type Node = keyof typeof N;
const mid = (a: Node, b: Node) => [(N[a][0] + N[b][0]) / 2, (N[a][1] + N[b][1]) / 2] as const;
const pathOf = (a: Node, b: Node) => `M${N[a][0]},${N[a][1]} L${N[b][0]},${N[b][1]}`;

const GREEN = "#10b981";
const YELLOW = "#eab308";
const RED = "#ef4444";

function Road({ from, to, color, cars, delay, dashed }: { from: Node; to: Node; color: string; cars: number; delay: number; dashed?: boolean }) {
  const d = pathOf(from, to);
  return (
    <g>
      <path d={d} stroke={color} strokeWidth={dashed ? 4 : 13} strokeLinecap="round" strokeDasharray={dashed ? "7 7" : undefined} fill="none" />
      {/* a white streak runs along the road in the driving direction and fades, only where cars drive */}
      {cars > 0 && <path d={d} pathLength={100} className="road-streak" style={{ animationDelay: `${delay}s` }} />}
    </g>
  );
}

function CarsBadge({ at, cars }: { at: readonly [number, number]; cars: number }) {
  const w = 36;
  return (
    <g transform={`translate(${at[0] - w / 2},${at[1] - 10})`}>
      <rect width={w} height={20} rx={10} fill="#0F172A" stroke="#ffffff" strokeWidth={1.5} />
      <Car x={6} y={4} size={12} color="#ffffff" strokeWidth={2.4} />
      <text x={25} y={14} textAnchor="middle" fill="#ffffff" fontSize="11" fontWeight="700" className="font-secondary">{cars}</text>
    </g>
  );
}

export default function CitizenBraessExplainerModal({ open, onClose }: Props) {
  const { t } = useI18n();
  const [shortcut, setShortcut] = useState(false);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setShortcut(false);
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const without = equilibrium(false);
  const withCut = equilibrium(true);
  const s = shortcut ? withCut : without;
  const diff = withCut.time - without.time;

  const routes = [
    { name: "A → C → D", cars: s.up, parts: [FLAT, s.cd], open: true },
    { name: "A → B → D", cars: s.down, parts: [s.ab, FLAT], open: true },
    { name: "A → B → C → D", cars: s.cut, parts: [s.ab, SHORT, s.cd], open: shortcut },
  ];

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="explainer-title" onClick={onClose}>
      <div className="max-h-[94vh] w-full max-w-[1040px] overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl animate-slideIn" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <h2 id="explainer-title" className="text-[18px] font-bold text-slate-900">{t.explain}</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{t.explainerIntro}</p>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label={t.close} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100">
            <X size={18} />
          </button>
        </div>

        {/* wide two-column layout so the whole explanation fits without scrolling; stacks on narrow screens */}
        <div className="mt-3 grid items-start gap-4 md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div>
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1" role="radiogroup" aria-label={t.explainerShortcut}>
          {[false, true].map((v) => (
            <button key={String(v)} type="button" role="radio" aria-checked={shortcut === v} onClick={() => setShortcut(v)}
              className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold transition duration-300 ${
                shortcut === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
              }`}>
              {v ? t.explainerStepWith : t.explainerStepWithout}
            </button>
          ))}
        </div>

        <svg viewBox="20 25 520 255" className="mt-3 w-full rounded-xl bg-slate-50" role="img"
          aria-label={`A → D: ${shortcut ? t.explainerStepWith : t.explainerStepWithout}, ${s.time} min`}>
          <Road from="A" to="C" color={GREEN} cars={s.up} delay={0} />
          <Road from="A" to="B" color={YELLOW} cars={s.down + s.cut} delay={0} />
          <Road from="B" to="C" color={shortcut ? RED : "#94a3b8"} cars={s.cut} delay={0.6} dashed={!shortcut} />
          <Road from="C" to="D" color={YELLOW} cars={s.up + s.cut} delay={1.2} />
          <Road from="B" to="D" color={GREEN} cars={s.down} delay={1.2} />

          <g fontSize="12" className="fill-slate-700">
            <text x="166" y="80" textAnchor="end" fontWeight="600">{t.explainerFlat}</text>
            <text x="394" y="226" fontWeight="600">{t.explainerFlat}</text>
            <text x="394" y="68" fontWeight="600">{t.explainerBusy}</text>
            <text x="394" y="84" fontStyle="italic">{t.explainerBusyRule}</text>
            <text x="166" y="226" textAnchor="end" fontWeight="600">{t.explainerBusy}</text>
            <text x="166" y="242" textAnchor="end" fontStyle="italic">{t.explainerBusyRule}</text>
            <text x="304" y="146" fontWeight="600">{t.explainerShortcut}</text>
            <text x="304" y="162" className="font-secondary">{shortcut ? `${SHORT} min` : t.explainerClosed}</text>
          </g>

          <CarsBadge at={mid("A", "C")} cars={s.up} />
          <CarsBadge at={mid("A", "B")} cars={s.down + s.cut} />
          <CarsBadge at={mid("C", "D")} cars={s.up + s.cut} />
          <CarsBadge at={mid("B", "D")} cars={s.down} />
          {shortcut && <CarsBadge at={mid("B", "C")} cars={s.cut} />}

          {(Object.keys(N) as Node[]).map((k) => (
            <g key={k}>
              <circle cx={N[k][0]} cy={N[k][1]} r="18" fill="#0F172A" stroke="#ffffff" strokeWidth="3" />
              <text x={N[k][0]} y={N[k][1] + 5} textAnchor="middle" fill="#ffffff" fontSize="14" fontWeight="700">{k}</text>
            </g>
          ))}
        </svg>

          <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
            <h3 className="text-[12.5px] font-semibold text-emerald-800">{t.explainerTakeawayTitle}</h3>
            <p className="mt-0.5 text-[12.5px] leading-relaxed text-slate-700">{t.explainerTakeaway}</p>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <h3 className="text-[12.5px] font-semibold text-slate-900">{t.explainerWhatHappens}</h3>
            <p className="mt-1 text-[12.5px] leading-relaxed text-slate-600">{shortcut ? t.explainerWithBody : t.explainerWithoutBody}</p>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <div className="text-[11.5px] text-slate-500">{t.explainerTripTime}</div>
            <div className="mt-0.5 flex items-baseline gap-1.5 font-secondary">
              <span className={`text-[26px] font-bold ${shortcut ? "text-red-700" : "text-emerald-700"}`}>{s.time}</span>
              <span className="text-[12px] text-slate-500">min</span>
            </div>
            <p className={`text-[11.5px] font-semibold ${shortcut ? "text-red-700" : "text-emerald-700"}`}>
              <span className="font-secondary">{diff}</span> {shortcut ? t.explainerSlower : t.explainerFaster}
            </p>
            <table className="mt-2 w-full text-left text-[11.5px]">
              <thead className="text-slate-500">
                <tr><th className="font-medium">{t.explainerRoute}</th><th className="text-right font-medium">{t.explainerCars}</th><th className="text-right font-medium">{t.explainerTime}</th></tr>
              </thead>
              <tbody className="text-slate-800">
                {routes.map((r) => (
                  <tr key={r.name} className={r.open && r.cars > 0 ? "" : "text-slate-400"}>
                    <td className="py-0.5">{r.name}</td>
                    <td className="py-0.5 text-right font-secondary">{r.open ? r.cars : "—"}</td>
                    <td className="py-0.5 text-right font-secondary">
                      {r.open ? `${r.parts.join(" + ")} = ${r.parts.reduce((a, b) => a + b, 0)} min` : t.explainerClosed}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] italic text-slate-400">{t.explainerNote}</p>
        </div>
        </div>
      </div>
    </div>
  );
}
