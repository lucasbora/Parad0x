type Tone = "neutral" | "live" | "seed" | "warn" | "gdpr";

interface Props {
  label: string;
  tone?: Tone;
  title?: string;
}

const TONES: Record<Tone, string> = {
  neutral: "border-slate-200 bg-slate-50 text-slate-600",
  live: "border-emerald-200 bg-emerald-50 text-emerald-800",
  seed: "border-slate-300 bg-white text-slate-600",
  warn: "border-amber-200 bg-amber-50 text-amber-800",
  gdpr: "border-sky-200 bg-sky-50 text-sky-800",
};

/** Compact monospace provenance pill: "SMTT GTFS v4.31 · Nov 2026". */
export default function SourceBadge({ label, tone = "neutral", title }: Props) {
  return (
    <span
      title={title ?? label}
      className={`inline-flex max-w-full items-center gap-1 truncate rounded-full border px-2 py-[1px] font-mono text-[10px] leading-4 ${TONES[tone]}`}
    >
      {(tone === "live" || tone === "seed") && (
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone === "live" ? "bg-emerald-500" : "bg-slate-400"}`} aria-hidden />
      )}
      <span className="truncate">{label}</span>
    </span>
  );
}
