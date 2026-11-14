import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, Minus, Play, Plus, Square, Trash2, X } from "lucide-react";
import type { BaselineLink, CorridorResponse, Profile } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { fmt } from "../api";

/** Columns exactly as backend/app/corridor/inputs.py SCHEMAS expects them. */
const SCHEMAS = {
  "gate_counts.csv": ["gate_id", "direction", "profile", "start", "end", "vehicles", "source", "notes"],
  "link_counts.csv": ["link_id", "profile", "start", "end", "vehicles", "source", "notes"],
  "turn_counts.csv": ["node_id", "from_link_id", "to_link_id", "profile", "start", "end", "vehicles", "source"],
} as const;
type CountFile = keyof typeof SCHEMAS;
type Kind = "gate" | "link" | "turn";
const FILE_OF: Record<Kind, CountFile> = { gate: "gate_counts.csv", link: "link_counts.csv", turn: "turn_counts.csv" };

interface Row {
  file: CountFile;
  values: Record<string, string>;
}

const STORE = "tmbg.counts.v1";
const INTERVAL_S = 15 * 60;

function load(): { rows: Row[]; observer: string } {
  try {
    const v = JSON.parse(window.localStorage.getItem(STORE) ?? "");
    return { rows: Array.isArray(v.rows) ? v.rows : [], observer: typeof v.observer === "string" ? v.observer : "" };
  } catch {
    return { rows: [], observer: "" };
  }
}

const hhmm = (d: Date) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
const isoDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const nodesOf = (linkId: string) => /^L(\d+)_(\d+)$/.exec(linkId)?.slice(1, 3) ?? [];

function toCsv(file: CountFile, rows: Row[]): string {
  const cols = SCHEMAS[file];
  const q = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return [cols.join(","), ...rows.filter((r) => r.file === file).map((r) => cols.map((c) => q(r.values[c] ?? "")).join(","))].join("\n") + "\n";
}

interface Props {
  open: boolean;
  data: CorridorResponse;
  profile: Profile;
  baseline: BaselineLink[] | null;
  onClose: () => void;
}

/** Field tally counter: count cars for one interval on a phone and get rows in the exact CSV format. */
export default function CountTool({ open, data, profile, baseline, onClose }: Props) {
  const { t, lang } = useI18n();
  const [kind, setKind] = useState<Kind>("gate");
  const [{ rows, observer }, setStore] = useState(load);
  const [gateId, setGateId] = useState("");
  const [direction, setDirection] = useState<"in" | "out">("in");
  const [linkId, setLinkId] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [fromLink, setFromLink] = useState("");
  const [toLink, setToLink] = useState("");
  const [notes, setNotes] = useState("");
  const [started, setStarted] = useState<Date | null>(null);
  const [count, setCount] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [confirmClear, setConfirmClear] = useState(false);
  const plusRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORE, JSON.stringify({ rows, observer }));
    } catch {
      /* storage unavailable: rows live until the page closes */
    }
  }, [rows, observer]);

  useEffect(() => {
    if (!started) return;
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [started]);

  const flow = useMemo(() => new Map((baseline ?? []).map((l) => [l.id, l.flow])), [baseline]);
  const linkFeat = useMemo(() => new Map(data.links.features.map((f) => [f.properties.id, f.properties])), [data]);
  const meta = data.profiles.find((p) => p.id === profile);

  // gates, busiest first (model estimate — only to prioritise where to stand)
  // gate id = "G" + outside node: the entering link starts there, the leaving link ends there
  const gates = useMemo(() => data.gates.features.map((g) => g.properties)
    .map((g) => {
      const node = g.id.slice(1);
      const est = data.links.features
        .filter((f) => nodesOf(f.properties.id).includes(node))
        .reduce((s, f) => s + (flow.get(f.properties.id) ?? 0), 0);
      return { ...g, est };
    })
    .sort((a, b) => b.est - a.est), [data, flow]);
  const gate = gates.find((g) => g.id === gateId);

  const insideLinks = useMemo(() => data.links.features.map((f) => f.properties)
    .filter((p) => p.inside && p.street !== "(fără nume)")
    .sort((a, b) => (flow.get(b.id) ?? 0) - (flow.get(a.id) ?? 0)).slice(0, 80), [data, flow]);

  const junctions = useMemo(() => data.junctions.features.map((f) => f.properties)
    .sort((a, b) => Number(b.signalized) - Number(a.signalized) || a.name.localeCompare(b.name)), [data]);
  const inLinks = useMemo(() => data.links.features.map((f) => f.properties).filter((p) => nodesOf(p.id)[1] === nodeId), [data, nodeId]);
  const outLinks = useMemo(() => data.links.features.map((f) => f.properties).filter((p) => nodesOf(p.id)[0] === nodeId), [data, nodeId]);

  useEffect(() => {
    if (gate && !(direction === "in" ? gate.needsIn : gate.needsOut)) setDirection(gate.needsIn ? "in" : "out");
  }, [gate, direction]);

  const target = useMemo((): Record<string, string> | null => {
    if (kind === "gate") return gate ? { gate_id: gate.id, direction } : null;
    if (kind === "link") return linkId ? { link_id: linkId } : null;
    return nodeId && fromLink && toLink ? { node_id: nodeId, from_link_id: fromLink, to_link_id: toLink } : null;
  }, [kind, gate, direction, linkId, nodeId, fromLink, toLink]);

  const ready = !!target && observer.trim().length > 1;
  const running = !!started;
  const elapsed = started ? Math.floor((now - started.getTime()) / 1000) : 0;

  const start = () => {
    setCount(0);
    setStarted(new Date());
    setNow(Date.now());
    window.setTimeout(() => plusRef.current?.focus(), 0);
  };
  const stop = useCallback(() => {
    if (!started || !target) return;
    const end = new Date();
    const row: Row = {
      file: FILE_OF[kind],
      values: {
        ...target, profile, start: hhmm(started), end: hhmm(end), vehicles: String(count),
        source: `tally ${observer.trim()} ${isoDate(started)}`, notes: notes.trim(),
      },
    };
    setStore((s) => ({ ...s, rows: [...s.rows, row] }));
    setStarted(null);
  }, [started, target, kind, profile, count, observer, notes]);

  useEffect(() => {
    if (!open || !running) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.key === " " || e.key === "Enter" || e.key === "+") {
        e.preventDefault();
        setCount((c) => c + 1);
      } else if (e.key === "Backspace" || e.key === "-") {
        e.preventDefault();
        setCount((c) => Math.max(0, c - 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, running]);

  const download = (file: CountFile) => {
    const blob = new Blob([toCsv(file, rows)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = file;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (!open) return null;
  const label = (id: string) => {
    const p = linkFeat.get(id);
    return p ? `${p.street} ${t.heading[p.heading] ?? p.heading}` : id;
  };
  const sel = "w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-[12.5px] text-slate-900";
  const files = (Object.keys(SCHEMAS) as CountFile[]).filter((f) => rows.some((r) => r.file === f));

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="count-title" onClick={onClose}>
      <div className="max-h-[94vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-4 shadow-2xl animate-slideIn" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <h2 id="count-title" className="text-[17px] font-bold text-slate-900">{t.countTitle}</h2>
            <p className="mt-0.5 text-[12px] leading-snug text-slate-600">{t.countIntro}</p>
            {meta && (
              <p className="mt-1 font-mono text-[11px] text-slate-500">
                {lang === "ro" ? meta.labelRo : meta.labelEn} · {meta.start}–{meta.end} ({meta.day === "sunday" ? t.countSunday : t.countWeekday})
              </p>
            )}
          </div>
          <button onClick={onClose} aria-label={t.close} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"><X size={17} /></button>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-0.5 text-[12px]" role="radiogroup">
          {(["gate", "link", "turn"] as Kind[]).map((k) => (
            <button key={k} role="radio" aria-checked={kind === k} disabled={running} onClick={() => setKind(k)}
              className={`rounded-md px-2 py-1.5 font-semibold transition disabled:opacity-50 ${kind === k ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}>
              {t.countKinds[k]}
            </button>
          ))}
        </div>
        <p className="mt-1 text-[11px] leading-snug text-slate-500">{t.countKindHint[kind]}</p>

        <div className="mt-2 space-y-2">
          {kind === "gate" && (
            <>
              <select className={sel} value={gateId} disabled={running} onChange={(e) => setGateId(e.target.value)} aria-label={t.countGate}>
                <option value="">{t.countGate}…</option>
                {gates.map((g) => (
                  <option key={g.id} value={g.id}>{g.side} · {g.street} {g.est > 0 ? `· ~${fmt(g.est, 0)} ${t.vehH} (${t.countModel})` : ""}</option>
                ))}
              </select>
              {gate && (
                <div className="flex gap-1">
                  {(["in", "out"] as const).filter((d) => (d === "in" ? gate.needsIn : gate.needsOut)).map((d) => (
                    <button key={d} disabled={running} onClick={() => setDirection(d)}
                      className={`flex-1 rounded-lg border px-2 py-1 text-[12px] font-semibold ${direction === d ? "border-[#005BBC] bg-blue-50 text-[#005BBC]" : "border-slate-300 text-slate-600"}`}>
                      {d === "in" ? t.inLabel : t.outLabel}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
          {kind === "link" && (
            <select className={sel} value={linkId} disabled={running} onChange={(e) => setLinkId(e.target.value)} aria-label={t.countLink}>
              <option value="">{t.countLink}…</option>
              {insideLinks.map((p) => (
                <option key={p.id} value={p.id}>{p.street} · {t.heading[p.heading] ?? p.heading} · {p.fromName} → {p.toName}</option>
              ))}
            </select>
          )}
          {kind === "turn" && (
            <>
              <select className={sel} value={nodeId} disabled={running} onChange={(e) => { setNodeId(e.target.value); setFromLink(""); setToLink(""); }} aria-label={t.countNode}>
                <option value="">{t.countNode}…</option>
                {junctions.map((j) => <option key={j.id} value={j.id}>{j.signalized ? "🚦 " : ""}{j.name}</option>)}
              </select>
              {nodeId && (
                <div className="grid grid-cols-2 gap-1">
                  <select className={sel} value={fromLink} disabled={running} onChange={(e) => setFromLink(e.target.value)} aria-label={t.countFrom}>
                    <option value="">{t.countFrom}…</option>
                    {inLinks.map((p) => <option key={p.id} value={p.id}>{label(p.id)}</option>)}
                  </select>
                  <select className={sel} value={toLink} disabled={running} onChange={(e) => setToLink(e.target.value)} aria-label={t.countTo}>
                    <option value="">{t.countTo}…</option>
                    {outLinks.map((p) => <option key={p.id} value={p.id}>{label(p.id)}</option>)}
                  </select>
                </div>
              )}
            </>
          )}
          <div className="grid grid-cols-2 gap-1">
            <input className={sel} value={observer} disabled={running} placeholder={t.countObserver}
              onChange={(e) => setStore((s) => ({ ...s, observer: e.target.value }))} aria-label={t.countObserver} />
            <input className={sel} value={notes} placeholder={t.countNotes} onChange={(e) => setNotes(e.target.value)} aria-label={t.countNotes} />
          </div>
        </div>

        <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-center">
          {!running ? (
            <button onClick={start} disabled={!ready}
              className="inline-flex items-center gap-2 rounded-lg bg-[#005BBC] px-4 py-2 text-[13px] font-semibold text-white shadow-sm disabled:opacity-40">
              <Play size={15} /> {t.countStart}
            </button>
          ) : (
            <>
              <p className={`font-mono text-[13px] ${elapsed >= INTERVAL_S ? "font-bold text-emerald-700" : "text-slate-600"}`}>
                {String(Math.floor(elapsed / 60)).padStart(2, "0")}:{String(elapsed % 60).padStart(2, "0")} / 15:00
                {elapsed >= INTERVAL_S && ` · ${t.countDone}`}
              </p>
              <div className="mt-2 flex items-center justify-center gap-2">
                <button onClick={() => setCount((c) => Math.max(0, c - 1))} aria-label="−1"
                  className="grid h-14 w-14 place-items-center rounded-xl border border-slate-300 bg-white text-slate-700"><Minus size={20} /></button>
                <button ref={plusRef} onClick={() => setCount((c) => c + 1)} aria-label="+1"
                  className="grid h-24 w-40 place-items-center rounded-2xl bg-[#005BBC] text-white shadow-md active:scale-95">
                  <span className="flex items-center gap-1 font-mono text-[34px] font-bold"><Plus size={22} />{count}</span>
                </button>
                <button onClick={stop} aria-label={t.countStop}
                  className="grid h-14 w-14 place-items-center rounded-xl border border-slate-300 bg-white text-red-700"><Square size={18} /></button>
              </div>
              <p className="mt-1 text-[10.5px] text-slate-500">{t.countKeys}</p>
            </>
          )}
          {!ready && !running && <p className="mt-1 text-[11px] text-slate-500">{t.countNeed}</p>}
        </div>

        {rows.length > 0 && (
          <div className="mt-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{t.countRows} ({rows.length})</p>
            <ul className="mt-1 max-h-40 divide-y divide-slate-100 overflow-y-auto text-[11.5px]">
              {rows.map((r, i) => (
                <li key={i} className="flex items-center gap-2 py-1">
                  <span className="font-mono text-[10.5px] text-slate-500">{r.file.replace("_counts.csv", "")}</span>
                  <span className="min-w-0 flex-1 truncate text-slate-700">
                    {r.values.gate_id ? `${gates.find((g) => g.id === r.values.gate_id)?.street ?? r.values.gate_id} (${r.values.direction})`
                      : r.values.link_id ? label(r.values.link_id) : `${label(r.values.from_link_id)} → ${label(r.values.to_link_id)}`}
                  </span>
                  <span className="font-mono text-slate-600">{r.values.profile} {r.values.start}–{r.values.end}</span>
                  <b className="w-10 text-right font-mono text-slate-900">{r.values.vehicles}</b>
                  <button onClick={() => setStore((s) => ({ ...s, rows: s.rows.filter((_, j) => j !== i) }))} aria-label={t.removePin}
                    className="text-slate-400 hover:text-red-700"><X size={13} /></button>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {files.map((f) => (
                <button key={f} onClick={() => download(f)}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2 py-1 font-mono text-[11px] text-slate-800 hover:bg-slate-50">
                  <Download size={12} /> {f}
                </button>
              ))}
              <button onClick={() => (confirmClear ? (setStore((s) => ({ ...s, rows: [] })), setConfirmClear(false)) : setConfirmClear(true))}
                className="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold text-red-700 hover:bg-red-50">
                <Trash2 size={12} /> {confirmClear ? t.countClearSure : t.countClear}
              </button>
            </div>
            <p className="mt-1 text-[10.5px] leading-snug text-slate-500">{t.countSave}</p>
          </div>
        )}
      </div>
    </div>
  );
}
