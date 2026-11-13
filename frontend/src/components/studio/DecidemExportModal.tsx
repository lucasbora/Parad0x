import { useEffect, useRef, useState } from "react";
import { Check, Copy, ExternalLink, Loader2, X } from "lucide-react";
import { api } from "../../api/client";
import { useI18n } from "../../i18n/translations";
import type { DecidemBriefResponse, SimulateRequest } from "../../types/simulator";
import DataProvenanceBadge from "./DataProvenanceBadge";

interface Props {
  open: boolean;
  request: SimulateRequest | null;
  onClose: () => void;
}

/** Bilingual policy brief, ready to paste into decidem.primariatm.ro. */
export default function DecidemExportModal({ open, request, onClose }: Props) {
  const { t, lang } = useI18n();
  const [brief, setBrief] = useState<DecidemBriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [which, setWhich] = useState<"ro" | "en">(lang);
  const [copied, setCopied] = useState(false);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open || !request) return;
    setBrief(null);
    setError(null);
    setWhich(lang);
    api.decidemBrief(request).then(setBrief).catch((e: Error) => setError(e.message));
    closeRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, request]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  const text = brief ? (which === "ro" ? brief.briefRo : brief.briefEn) : "";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: user can still select the text */
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="decidem-title" onClick={onClose}>
      <div className="flex max-h-[88vh] w-full max-w-2xl flex-col rounded-2xl bg-white p-5 shadow-2xl animate-slideIn" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-3">
          <div className="flex-1">
            <h2 id="decidem-title" className="text-[17px] font-bold text-slate-900">{t.decidemTitle}</h2>
            <p className="mt-0.5 text-[12px] text-slate-500">{t.owners}</p>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label={t.close} className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 hover:bg-slate-100">
            <X size={18} />
          </button>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <div className="flex rounded-lg bg-slate-100 p-0.5 font-mono text-[11px]" role="radiogroup">
            {(["ro", "en"] as const).map((l) => (
              <button key={l} role="radio" aria-checked={which === l} onClick={() => setWhich(l)}
                className={`rounded-md px-2 py-1 font-semibold uppercase ${which === l ? "bg-white text-[#005BBC] shadow-sm" : "text-slate-500"}`}>
                {l}
              </button>
            ))}
          </div>
          {brief && brief.codGis.map((c) => <DataProvenanceBadge key={c} label={`codGis #${c}`} />)}
          <div className="flex-1" />
          <button onClick={copy} disabled={!brief}
            className="flex items-center gap-1.5 rounded-lg bg-[#005BBC] px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-[#004a99] disabled:opacity-40">
            {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? t.copied : t.copy}
          </button>
        </div>
        <div className="mt-3 min-h-[200px] flex-1 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3">
          {!brief && !error && (
            <div className="flex items-center gap-2 text-[12px] text-slate-500"><Loader2 size={14} className="animate-spin" /> {t.generating}</div>
          )}
          {error && <p className="text-[12px] text-red-700">{error}</p>}
          {brief && <pre className="whitespace-pre-wrap break-words font-mono text-[11.5px] leading-relaxed text-slate-800">{text}</pre>}
        </div>
        {brief && (
          <div className="mt-3 flex flex-wrap gap-2">
            <a href={brief.decidemUrl} target="_blank" rel="noreferrer"
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-[12px] font-medium text-[#005BBC] hover:bg-blue-50">
              <ExternalLink size={13} /> {t.openDecidem}
            </a>
            <a href={brief.sesizariUrl} target="_blank" rel="noreferrer"
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-[12px] font-medium text-[#005BBC] hover:bg-blue-50">
              <ExternalLink size={13} /> {t.openSesizari}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
