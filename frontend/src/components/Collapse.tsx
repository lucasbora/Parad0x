import { useEffect, useRef, type ReactNode } from "react";

/** Smooth height open/close (CSS grid 0fr → 1fr). Closed content stays mounted but is inert. */
export default function Collapse({ open, children, className = "" }: { open: boolean; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    ref.current?.toggleAttribute("inert", !open);
  }, [open]);
  return (
    <div
      ref={ref}
      aria-hidden={!open}
      className={`grid transition-[grid-template-rows,opacity] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
        open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
      } ${className}`}
    >
      <div className="min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}
