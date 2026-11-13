import { useEffect, useRef, useState } from "react";
import { BookOpen, Loader2, MapPin, Search } from "lucide-react";
import { api } from "../../api/client";
import { useI18n } from "../../i18n/translations";
import type { HealthResponse, NetworkResponse, StreetSearchResult } from "../../types/simulator";
import DataProvenanceBadge from "./DataProvenanceBadge";

interface Props {
  network: NetworkResponse | null;
  health: HealthResponse | null;
  onPickStreet: (r: StreetSearchResult) => void;
  onExplain: () => void;
}

/** Brand row + diacritic-free street search (PMT Nomenclator) + RO/EN toggle. */
export default function TopNavbar({ network, health, onPickStreet, onExplain }: Props) {
  const { t, lang, setLang } = useI18n();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<StreetSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const ctrl = new AbortController();
    const id = window.setTimeout(() => {
      setBusy(true);
      api
        .searchStreets(q, ctrl.signal)
        .then((r) => {
          setResults(r.results);
          setActive(0);
          setOpen(true);
        })
        .catch(() => undefined)
        .finally(() => setBusy(false));
    }, 180);
    return () => {
      ctrl.abort();
      window.clearTimeout(id);
    };
  }, [q]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (r: StreetSearchResult) => {
    onPickStreet(r);
    setQ(r.denumireCompleta);
    setOpen(false);
  };

  const nomenProv = network?.provenance.find((p) => p.dataset === "nomenclator");
  const live = health ? Object.values(health.cache).filter((c) => c.source !== "seed").length : 0;
  const total = health ? Object.keys(health.cache).length : 0;

  return (
    <header className="pointer-events-auto rounded-2xl border border-slate-200/80 bg-white/95 p-3 shadow-island backdrop-blur">
      <div className="flex items-center gap-2.5">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#005BBC] text-white shadow-sm" aria-hidden>
          <svg viewBox="0 0 32 32" className="h-6 w-6">
            <path d="M6 24 L16 8 L26 24 Z" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinejoin="round" />
            <path d="M11 16 L21 16" stroke="#34d399" strokeWidth="2.6" strokeLinecap="round" strokeDasharray="2 3" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[15px] font-bold leading-tight tracking-tight text-[#0F172A]">{t.appName}</h1>
          <p className="truncate text-[11.5px] text-slate-500">{t.appTagline}</p>
        </div>
        <button
          onClick={onExplain}
          className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-[#005BBC] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#005BBC]"
          title={t.explainBraess}
          aria-label={t.explainBraess}
        >
          <BookOpen size={16} />
        </button>
        <div className="flex rounded-lg bg-slate-100 p-0.5 font-mono text-[11px]" role="radiogroup" aria-label={t.language}>
          {(["ro", "en"] as const).map((l) => (
            <button
              key={l}
              role="radio"
              aria-checked={lang === l}
              onClick={() => setLang(l)}
              className={`rounded-md px-2 py-1 font-semibold uppercase transition ${
                lang === l ? "bg-white text-[#005BBC] shadow-sm" : "text-slate-500 hover:text-slate-800"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      <div ref={boxRef} className="relative mt-2.5">
        <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          onKeyDown={(e) => {
            if (!open || !results.length) return;
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              pick(results[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder={t.searchPlaceholder}
          aria-label={t.searchPlaceholder}
          role="combobox"
          aria-expanded={open}
          aria-controls="street-results"
          className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-8 pr-8 text-[13px] text-slate-900 placeholder:text-slate-400 focus:border-[#005BBC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#005BBC]/20"
        />
        {busy && <Loader2 size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 animate-spin text-slate-400" />}
        {open && (
          <ul
            id="street-results"
            role="listbox"
            className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-slate-200 bg-white py-1 shadow-island"
          >
            {results.length === 0 && <li className="px-3 py-2 text-[12px] text-slate-500">{t.searchNoResults}</li>}
            {results.map((r, i) => (
              <li
                key={`${r.codGis}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(r);
                }}
                onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-center gap-2 px-3 py-1.5 text-[12.5px] ${i === active ? "bg-blue-50" : ""}`}
              >
                <MapPin size={13} className={r.linkId ? "text-[#005BBC]" : "text-slate-300"} aria-hidden />
                <span className="flex-1 truncate">
                  <span className="text-slate-900">{r.denumireCompleta}</span>
                  {r.cartier && <span className="ml-1 text-slate-400">· {r.cartier}</span>}
                  {!r.linkId && <span className="ml-1 text-[10.5px] italic text-slate-400">({t.searchNotInModel})</span>}
                </span>
                <span className="font-mono text-[10.5px] text-slate-400">#{r.codGis}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <DataProvenanceBadge
          label={`PMT Nomenclator Străzi · ${nomenProv?.source ?? "seed"}`}
          tone={nomenProv && nomenProv.source !== "seed" ? "live" : "seed"}
        />
        {network && <DataProvenanceBadge label={`SMTT GTFS v${network.feedVersion} · Nov 2026`} tone="neutral" />}
        {health && <DataProvenanceBadge label={`PMT API ${live}/${total} live`} tone={live > 0 ? "live" : "seed"} />}
      </div>
    </header>
  );
}
