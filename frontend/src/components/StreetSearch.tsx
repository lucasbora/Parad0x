import { useEffect, useMemo, useRef, useState } from "react";
import { MapPin, Search, X } from "lucide-react";
import type { CorridorResponse } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  data: CorridorResponse;
  street: string | null;
  heading: string | null;
  onChange: (street: string | null, heading: string | null) => void;
}

/** "Calea Circumvalațiunii" → "calea circumvalatiunii" (so people can type without diacritics). */
export function norm(s: string): string {
  return s
    .replace(/[șşȘŞ]/g, "s")
    .replace(/[țţȚŢ]/g, "t")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

export default function StreetSearch({ data, street, heading, onChange }: Props) {
  const { t } = useI18n();
  const [q, setQ] = useState(street ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement | null>(null);

  useEffect(() => setQ(street ?? ""), [street]);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const matches = useMemo(() => {
    const n = norm(q);
    const all = data.streets;
    if (!n || n === norm(street ?? "")) return all.slice(0, 8);
    const words = n.split(/\s+/);
    return all.filter((s) => words.every((w) => norm(s.street).includes(w))).slice(0, 8);
  }, [q, data, street]);

  const pick = (name: string) => {
    const s = data.streets.find((x) => x.street === name);
    if (!s) return;
    onChange(s.street, s.directions.length === 1 ? s.directions[0].heading : null);
    setOpen(false);
  };

  const choice = data.streets.find((s) => s.street === street) ?? null;

  return (
    <section>
      <h2 className="text-[14px] font-semibold text-slate-900">{t.step1}</h2>
      <div ref={box} className="relative mt-2">
        <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, matches.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && matches[active]) {
              e.preventDefault();
              pick(matches[active].street);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder={t.search}
          aria-label={t.search}
          role="combobox"
          aria-expanded={open}
          aria-controls="street-list"
          className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-8 text-[13px] focus:border-[#005BBC] focus:outline-none focus:ring-2 focus:ring-[#005BBC]/20"
        />
        {q && (
          <button
            onClick={() => {
              setQ("");
              onChange(null, null);
            }}
            aria-label={t.close}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:text-slate-700"
          >
            <X size={14} />
          </button>
        )}
        {open && (
          <ul id="street-list" role="listbox" className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            {matches.length === 0 && <li className="px-3 py-2 text-[12px] text-slate-500">{t.noMatches}</li>}
            {matches.map((s, i) => (
              <li
                key={s.street}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(s.street);
                }}
                onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-center gap-2 px-3 py-1.5 text-[12.5px] ${i === active ? "bg-blue-50" : ""}`}
              >
                <MapPin size={13} className={data.corridor.mainStreets.includes(s.street) ? "text-[#005BBC]" : "text-slate-400"} />
                <span className="flex-1 truncate">{s.street}</span>
                <span className="font-secondary text-[10.5px] text-slate-400">{s.directions.map((d) => d.heading).join(" · ")}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-1 text-[11px] text-slate-500">{t.orClickMap}</p>

      {choice && (
        <div className="mt-2">
          <p className="text-[12px] font-medium text-slate-700">{t.direction}</p>
          <div className="mt-1 flex flex-wrap gap-1.5" role="radiogroup">
            {choice.directions.map((d) => (
              <button
                key={d.heading}
                role="radio"
                aria-checked={d.heading === heading}
                onClick={() => onChange(choice.street, d.heading)}
                className={`rounded-full border px-3 py-1 text-[12px] font-medium ${
                  d.heading === heading ? "border-[#005BBC] bg-[#005BBC] text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                {t.heading[d.heading] ?? d.heading}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
