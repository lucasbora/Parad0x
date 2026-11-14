import { useEffect, useRef, useState } from "react";
import { Bike, Bus, Car, Loader2, RotateCcw, TreeDeciduous } from "lucide-react";
import type { LaneKind } from "../types/corridor";
import { useI18n } from "../i18n/translations";
import { usePresence } from "../motion";

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
// car lane centre line: whole white dashes only ("space" never cuts a dash in half at the ends)
const DASH_STYLE = {
  backgroundImage: "linear-gradient(rgba(255,255,255,0.9), rgba(255,255,255,0.9))",
  backgroundSize: "3px 12px",
  backgroundRepeat: "no-repeat space",
} as const;

function LaneStrip({
  kind,
  typeName,
  label,
  open,
  mergeLeft,
  mergeRight,
  onClick,
}: {
  kind: LaneKind | "busExisting";
  typeName: string;
  label?: string;
  open?: boolean;
  mergeLeft?: boolean;
  mergeRight?: boolean;
  onClick?: () => void;
}) {
  const k: LaneKind = kind === "busExisting" ? "bus" : kind;
  const Icon = ICON[k];
  const isSidewalk = k === "sidewalk";
  const radiusClass = `${mergeLeft ? "rounded-l-none" : "rounded-l-md"} ${mergeRight ? "rounded-r-none" : "rounded-r-md"}`;

  const iconAndName = (
    <div key={`${k}-content`} className="m-swap-in flex flex-col items-center justify-center gap-1.5 px-1">
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
  );

  const content = (
    <>
      {k === "bike" && <div className="m-fade-in pointer-events-none absolute inset-x-1 inset-y-0 border-x-[3px] border-white/80" />}
      {/* keyed by lane type, so a new type replays its markings */}
      {k === "car" ? (
        // dashed centre line, painted from the bottom up, with the icon and name sitting in its gap
        <div key="car" className="absolute inset-0 flex flex-col items-center">
          <span className="m-paint-up w-[3px] flex-1" style={{ ...DASH_STYLE, animationDelay: "170ms" }} />
          <div className="py-2">{iconAndName}</div>
          <span className="m-paint-up w-[3px] flex-1" style={DASH_STYLE} />
        </div>
      ) : k === "bus" ? (
        // road marking: a long arrow, the bus, and "BUS" painted letter by letter (more room at the bottom when a label sits there)
        <div key="bus" className={`flex flex-col items-center gap-1.5 px-1 ${label ? "pb-9" : "pb-2"}`}>
          <svg viewBox="0 0 16 48" className={`m-paint-up w-3.5 ${label ? "h-6" : "h-9"}`}
            style={{ animationDuration: "320ms" }} aria-hidden="true">
            <polygon points="8,0 15.5,15 10,15 10,48 6,48 6,15 0.5,15" fill="#ffffff" />
          </svg>
          <Icon size={22} className="m-swap-in drop-shadow-sm" style={{ color: "#ffffff" }} strokeWidth={2.2} />
          <span className="sr-only">{typeName}</span>
          <span aria-hidden="true" className="my-1.5 flex gap-[2px] text-[13px] font-extrabold leading-none text-white">
            {"BUS".split("").map((ch, i) => (
              <span key={i} className="m-paint-up inline-block scale-y-[1.8]" style={{ animationDelay: `${300 + i * 140}ms` }}>{ch}</span>
            ))}
          </span>
        </div>
      ) : (
        iconAndName
      )}
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
      className={`relative flex h-36 w-full flex-1 items-center justify-center overflow-hidden transition-[background-color,box-shadow,transform,filter] duration-500 active:scale-[0.97] active:duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#005BBC] ${radiusClass} ${
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
  const menu = usePresence(menuFor !== null, 140);
  const lastMenu = useRef<number | null>(null);
  if (menuFor !== null) lastMenu.current = menuFor;
  const menuShownFor = menuFor ?? lastMenu.current;
  const changed = lanes.some((l, i) => l !== original[i]);
  // with more than three lane strips the dropdown is too narrow for the names, so it shows icons only
  const iconOnly = lanes.length + (existingBusLane ? 1 : 0) > 3;

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
    <section className="m-rise-in">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[14px] font-semibold text-slate-900">{t.step2}</h2>
        {busy && (
          <span className="m-fade-in flex items-center gap-1 text-[11px] text-slate-500">
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

            return (
              <div
                key={i}
                className={`m-rise-in relative flex flex-1 ${mergeLeft ? "ml-0" : "ml-1"}`}
                style={{ animationDelay: `${120 + i * 50}ms` }}
              >
                <LaneStrip
                  kind={l}
                  typeName={t.laneKinds[l]}
                  open={menuFor === i}
                  mergeLeft={mergeLeft}
                  mergeRight={mergeRight}
                  onClick={() => setMenuFor(menuFor === i ? null : i)}
                />
                {menu.mounted && menuShownFor === i && (
                  <div
                    role="menu"
                    className={`absolute left-0 top-full z-30 mt-1.5 flex w-full origin-top flex-col gap-1 rounded-xl border border-slate-200/90 bg-white p-1 shadow-island ${
                      menu.closing ? "pointer-events-none m-pop-out" : "m-pop-in"
                    }`}
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
                          aria-label={iconOnly ? t.laneKinds[opt] : undefined}
                          title={iconOnly ? t.laneKinds[opt] : undefined}
                          onClick={() => {
                            const next = [...lanes];
                            next[i] = opt;
                            onChange(next);
                            setMenuFor(null);
                          }}
                          className={`flex w-full items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-[11.5px] font-semibold transition hover:brightness-110 active:scale-95 ${
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
                          {!iconOnly && <span className="truncate">{t.laneKinds[opt]}</span>}
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
          className="m-fade-in mt-2 flex items-center gap-1 text-[11.5px] font-medium text-slate-500 transition-colors hover:text-slate-900"
        >
          <RotateCcw size={11} /> {t.resetLanes}
        </button>
      )}
    </section>
  );
}
