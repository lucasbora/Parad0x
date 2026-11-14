import { useEffect, useRef, useState } from "react";
import { Bike, Bus, Car, Loader2, RotateCcw, TreeDeciduous } from "lucide-react";
import type { LaneKind } from "../types/corridor";
import { useI18n } from "../i18n/translations";

interface Props {
  lanes: LaneKind[];
  original: LaneKind[];
  existingBusLane: boolean;
  segments: number;
  lanesSource: string;
  slowness: number;
  busy: boolean;
  onChange: (lanes: LaneKind[]) => void;
}

const KINDS: LaneKind[] = ["car", "bus", "bike", "sidewalk"];
const ICON = { car: Car, bus: Bus, bike: Bike, sidewalk: TreeDeciduous } as const;
const SURFACE: Record<LaneKind, string> = {
  car: "#334155",
  bus: "#991b1b",
  bike: "#047857",
  sidewalk: "#cbd5e1",
};

function LaneStrip({
  kind,
  typeName,
  label,
  open,
  mergeLeft,
  mergeRight,
  showDivider,
  onClick,
}: {
  kind: LaneKind | "busExisting";
  typeName: string;
  label?: string;
  open?: boolean;
  mergeLeft?: boolean;
  mergeRight?: boolean;
  showDivider?: boolean;
  onClick?: () => void;
}) {
  const k: LaneKind = kind === "busExisting" ? "bus" : kind;
  const Icon = ICON[k];
  const isSidewalk = k === "sidewalk";
  const radiusClass = `${mergeLeft ? "rounded-l-none" : "rounded-l-md"} ${mergeRight ? "rounded-r-none" : "rounded-r-md"}`;

  const content = (
    <>
      {showDivider && !isSidewalk && (
        <div
          className="absolute inset-y-0 right-0 w-[2px]"
          style={{
            backgroundImage: "repeating-linear-gradient(to bottom, rgba(255,255,255,0.75) 0 10px, transparent 10px 20px)",
          }}
        />
      )}
      {k === "bike" && <div className="pointer-events-none absolute inset-x-1 inset-y-0 border-x-[3px] border-white/80" />}
      <div className="flex flex-col items-center justify-center gap-1.5 px-1">
        <Icon
          size={22}
          className={isSidewalk ? "" : "drop-shadow-sm"}
          style={{ color: isSidewalk ? "#047857" : "#ffffff" }}
          strokeWidth={2.2}
        />
        <span
          className="text-center text-[11px] font-semibold leading-tight"
          style={{ color: isSidewalk ? "#0f172a" : "#ffffff" }}
        >
          {typeName}
        </span>
      </div>
      {label && (
        <span className="absolute inset-x-0 bottom-0 bg-black/35 py-0.5 text-center text-[8.5px] font-semibold uppercase tracking-wide text-white">
          {label}
        </span>
      )}
    </>
  );

  if (!onClick) {
    return (
      <div
        className={`relative flex h-36 flex-1 items-center justify-center overflow-hidden transition-[background-color,box-shadow] duration-500 ${radiusClass}`}
        style={{ backgroundColor: SURFACE[k], opacity: kind === "busExisting" ? 0.85 : 1 }}
      >
        {content}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-haspopup="menu"
      aria-expanded={open}
      className={`relative flex h-36 w-full flex-1 items-center justify-center overflow-hidden transition-[background-color,box-shadow] duration-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#005BBC] ${radiusClass} ${
        open ? "z-10 ring-2 ring-[#005BBC]" : "hover:brightness-95"
      }`}
      style={{ backgroundColor: SURFACE[k] }}
    >
      {content}
    </button>
  );
}

export default function LaneMixer({
  lanes,
  original,
  existingBusLane,
  segments,
  lanesSource,
  busy,
  onChange,
}: Props) {
  const { t } = useI18n();
  const [menuFor, setMenuFor] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const changed = lanes.some((l, i) => l !== original[i]);

  useEffect(() => {
    if (menuFor === null) return;
    const onDoc = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setMenuFor(null);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuFor(null);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  const firstIsSidewalk = lanes.length > 0 && lanes[0] === "sidewalk";
  const lastIsSidewalk = !existingBusLane && lanes.length > 0 && lanes[lanes.length - 1] === "sidewalk";

  return (
    <section>
      <div className="flex items-baseline justify-between">
        <h2 className="text-[14px] font-semibold text-slate-900">{t.step2}</h2>
        {busy && (
          <span className="flex items-center gap-1 text-[11px] text-slate-500">
            <Loader2 size={12} className="animate-spin" /> {t.recalculating}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-[11px] text-slate-500">
        {segments} {t.segments} · {lanesSource === "field check" ? t.fieldCheck : t.fromOsm} · {t.liveHint}
      </p>

      <div ref={containerRef} className="mt-2 rounded-xl bg-slate-100 p-2">
        <div className="flex items-stretch">
          {/* Left outer sidewalk */}
          <div
            className={`flex w-7 shrink-0 flex-col items-center justify-center transition-[background-color] duration-500 ${
              firstIsSidewalk ? "rounded-l-md rounded-r-none" : "rounded-md"
            }`}
            style={{ backgroundColor: SURFACE.sidewalk }}
          >
            {!firstIsSidewalk && <TreeDeciduous size={15} style={{ color: "#047857" }} />}
          </div>

          {lanes.map((l, i) => {
            const prevIsSidewalk = i === 0 ? true : lanes[i - 1] === "sidewalk";
            const nextIsSidewalk =
              i === lanes.length - 1 ? !existingBusLane : lanes[i + 1] === "sidewalk";
            const mergeLeft = l === "sidewalk" && prevIsSidewalk;
            const mergeRight = l === "sidewalk" && nextIsSidewalk;
            const showDivider = l !== "sidewalk" && (i < lanes.length - 1 ? lanes[i + 1] !== "sidewalk" : existingBusLane);

            return (
              <div
                key={i}
                className={`relative flex flex-1 ${mergeLeft ? "ml-0" : "ml-1"}`}
              >
                <LaneStrip
                  kind={l}
                  typeName={t.laneKinds[l]}
                  open={menuFor === i}
                  mergeLeft={mergeLeft}
                  mergeRight={mergeRight}
                  showDivider={showDivider}
                  onClick={() => setMenuFor(menuFor === i ? null : i)}
                />
                {menuFor === i && (
                  <div
                    role="menu"
                    className=" -translate-x-0 absolute left-0 top-full z-30 mt-1.5 flex w-full flex-col gap-1 rounded-xl border border-slate-200/90 bg-white p-1 shadow-island animate-slideIn"
                  >
                    {KINDS.map((opt) => {
                      const OptIcon = ICON[opt];
                      const optSidewalk = opt === "sidewalk";
                      const active = l === opt;
                      return (
                        <button
                          key={opt}
                          type="button"
                          role="menuitemradio"
                          aria-checked={active}
                          onClick={() => {
                            const next = [...lanes];
                            next[i] = opt;
                            onChange(next);
                            setMenuFor(null);
                          }}
                          className={`flex w-full items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-[11.5px] font-semibold transition hover:brightness-110 ${
                            active ? "ring-2 ring-[#005BBC] ring-offset-1" : ""
                          }`}
                          style={{ backgroundColor: SURFACE[opt], color: optSidewalk ? "#0f172a" : "#ffffff" }}
                        >
                          <OptIcon
                            size={15}
                            className="shrink-0"
                            style={{ color: optSidewalk ? "#047857" : "#ffffff" }}
                            strokeWidth={2.2}
                          />
                          <span className="truncate">{t.laneKinds[opt]}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {existingBusLane && (
            <div className="ml-1 flex flex-1">
              <LaneStrip
                kind="busExisting"
                typeName={t.laneKinds.bus}
                label={t.existingBus}
              />
            </div>
          )}

          {/* Right outer sidewalk */}
          <div
            className={`flex w-7 shrink-0 flex-col items-center justify-center transition-[background-color] duration-500 ${
              lastIsSidewalk ? "ml-0 rounded-l-none rounded-r-md" : "ml-1 rounded-md"
            }`}
            style={{ backgroundColor: SURFACE.sidewalk }}
          >
            {!lastIsSidewalk && <TreeDeciduous size={15} style={{ color: "#047857" }} />}
          </div>
        </div>
      </div>

      {changed && (
        <button
          type="button"
          onClick={() => {
            setMenuFor(null);
            onChange(original);
          }}
          className="mt-2 flex items-center gap-1 text-[11.5px] font-medium text-slate-500 hover:text-slate-900"
        >
          <RotateCcw size={11} /> {t.resetLanes}
        </button>
      )}
    </section>
  );
}
