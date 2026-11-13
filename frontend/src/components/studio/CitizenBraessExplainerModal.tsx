import { useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { useI18n } from "../../i18n/translations";
import { fmt } from "../../lib/format";

interface Props {
  open: boolean;
  onClose: () => void;
}

/**
 * Classic Braess diamond, solved exactly:
 *   S→A: z/100 min (congestible)   A→T: 45 min (long but wide)
 *   S→B: 45 min                    B→T: z/100 min
 *   A→B shortcut: c min
 */
const C_SHORTCUT = 2;
const FIXED = 45;

function equilibrium(d: number, shortcut: boolean) {
  if (!shortcut) {
    const u = d / 2;
    return { u, l: d / 2, s: 0, time: u / 100 + FIXED };
  }
  const cap = 100 * (FIXED - C_SHORTCUT); // flow where a congestible leg costs as much as the detour
  if (d <= cap) return { u: 0, l: 0, s: d, time: (2 * d) / 100 + C_SHORTCUT };
  if (d <= 2 * cap) {
    const u = d - cap;
    const s = 2 * cap - d;
    return { u, l: u, s, time: (u + s) / 100 + FIXED };
  }
  const u = d / 2;
  return { u, l: u, s: 0, time: u / 100 + FIXED };
}

const P = { S: [40, 140], A: [210, 40], B: [210, 240], T: [380, 140] } as const;

function Dots({ path, n, color, dur }: { path: string; n: number; color: string; dur: number }) {
  return (
    <>
      {Array.from({ length: n }).map((_, i) => (
        <circle key={i} r="4" fill={color} stroke="#fff" strokeWidth="1">
          <animateMotion dur={`${dur}s`} repeatCount="indefinite" begin={`${(-dur * i) / Math.max(n, 1)}s`} path={path} />
        </circle>
      ))}
    </>
  );
}

export default function CitizenBraessExplainerModal({ open, onClose }: Props) {
  const { t } = useI18n();
  const [demand, setDemand] = useState(4000);
  const [shortcut, setShortcut] = useState(true);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const withCut = useMemo(() => equilibrium(demand, true), [demand]);
  const without = useMemo(() => equilibrium(demand, false), [demand]);
  const cur = shortcut ? withCut : without;
  const paradox = withCut.time > without.time + 1e-9 && withCut.s > 0;
  if (!open) return null;

  const upper = `M${P.S[0]},${P.S[1]} L${P.A[0]},${P.A[1]} L${P.T[0]},${P.T[1]}`;
  const lower = `M${P.S[0]},${P.S[1]} L${P.B[0]},${P.B[1]} L${P.T[0]},${P.T[1]}`;
  const cut = `M${P.S[0]},${P.S[1]} L${P.A[0]},${P.A[1]} L${P.B[0]},${P.B[1]} L${P.T[0]},${P.T[1]}`;
  const w = (z: number) => 2 + (z / demand) * 12;
  const dots = (z: number) => Math.round((z / demand) * 9);
  const dur = 2 + cur.time / 20;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="explainer-title" onClick={onClose}>
      <div className="max-h-[94vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl animate-slideIn" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <h2 id="explainer-title" className="text-[18px] font-bold text-slate-900">{t.explainBraess}</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{t.explainerIntro}</p>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label={t.close} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100">
            <X size={18} />
          </button>
        </div>

        <svg viewBox="0 0 420 280" className="mt-3 w-full rounded-xl bg-slate-50" role="img" aria-label="Braess diamond network">
          <line x1={P.S[0]} y1={P.S[1]} x2={P.A[0]} y2={P.A[1]} stroke="#f59e0b" strokeWidth={w(cur.u + cur.s)} strokeLinecap="round" />
          <line x1={P.A[0]} y1={P.A[1]} x2={P.T[0]} y2={P.T[1]} stroke="#3b82f6" strokeWidth={w(cur.u)} strokeLinecap="round" />
          <line x1={P.S[0]} y1={P.S[1]} x2={P.B[0]} y2={P.B[1]} stroke="#3b82f6" strokeWidth={w(cur.l)} strokeLinecap="round" />
          <line x1={P.B[0]} y1={P.B[1]} x2={P.T[0]} y2={P.T[1]} stroke="#f59e0b" strokeWidth={w(cur.l + cur.s)} strokeLinecap="round" />
          <line x1={P.A[0]} y1={P.A[1]} x2={P.B[0]} y2={P.B[1]} stroke={shortcut ? "#d946ef" : "#cbd5e1"} strokeWidth={shortcut ? w(cur.s) : 3} strokeDasharray={shortcut ? undefined : "6 6"} strokeLinecap="round" />
          <Dots path={upper} n={dots(cur.u)} color="#1d4ed8" dur={dur} />
          <Dots path={lower} n={dots(cur.l)} color="#1d4ed8" dur={dur} />
          {shortcut && <Dots path={cut} n={dots(cur.s)} color="#a21caf" dur={dur} />}
          {(Object.keys(P) as (keyof typeof P)[]).map((k) => (
            <g key={k}>
              <circle cx={P[k][0]} cy={P[k][1]} r="15" fill="#0F172A" />
              <text x={P[k][0]} y={P[k][1] + 4} textAnchor="middle" fill="#fff" fontSize="12" fontWeight="700">{k}</text>
            </g>
          ))}
          <g fontSize="10" className="font-mono" fill="#334155">
            <text x="95" y="78">z/100 min</text>
            <text x="300" y="78">45 min</text>
            <text x="95" y="215">45 min</text>
            <text x="300" y="215">z/100 min</text>
            <text x="218" y="145" fill={shortcut ? "#a21caf" : "#94a3b8"}>{C_SHORTCUT} min</text>
          </g>
        </svg>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="demand" className="text-[12px] font-semibold text-slate-700">
              {t.explainerDemand}: <span className="font-mono">{demand}</span>
            </label>
            <input id="demand" type="range" min={1000} max={8000} step={100} value={demand}
              onChange={(e) => setDemand(Number(e.target.value))} className="mt-1 w-full accent-[#005BBC]" />
            <label className="mt-2 flex cursor-pointer items-center gap-2 text-[12.5px] text-slate-800">
              <input type="checkbox" checked={shortcut} onChange={(e) => setShortcut(e.target.checked)} className="h-4 w-4 accent-[#d946ef]" />
              {t.explainerShortcut}
            </label>
            <div className="mt-2 grid grid-cols-3 gap-1 font-mono text-[10.5px] text-slate-600">
              <span>{t.explainerUpper}: {fmt(cur.u, 0)}</span>
              <span>{t.explainerLower}: {fmt(cur.l, 0)}</span>
              <span className="text-fuchsia-700">{t.explainerCut}: {fmt(cur.s, 0)}</span>
            </div>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <div className="text-[11.5px] text-slate-500">{t.explainerTravelTime}</div>
            <div className="mt-1 flex items-baseline gap-3 font-mono">
              <span className={`text-[22px] font-semibold ${shortcut ? "text-fuchsia-700" : "text-slate-400"}`}>{fmt(withCut.time, 1)}</span>
              <span className="text-slate-400">vs</span>
              <span className={`text-[22px] font-semibold ${!shortcut ? "text-[#059669]" : "text-slate-400"}`}>{fmt(without.time, 1)}</span>
              <span className="text-[11px] text-slate-500">min</span>
            </div>
            <div className="mt-1 text-[11px] text-slate-500">
              {t.explainerTotal}: <span className="font-mono">{fmt((cur.time * demand) / 60, 0)} veh·h</span>
            </div>
            <div className={`mt-2 rounded-lg px-2 py-1.5 text-[12px] font-semibold ${paradox ? "bg-fuchsia-50 text-fuchsia-800" : "bg-slate-100 text-slate-600"}`}>
              {paradox ? t.explainerParadox : t.explainerNoParadox}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
