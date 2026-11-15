/**
 * Small motion toolkit shared by the whole UI.
 *  - usePresence: keeps an element mounted while its exit animation plays
 *  - useSlidingThumb: the highlight that slides between the options of a segmented control
 *  - useTween: animates a number between values
 *  - animateEl / withViewTransition: one-off animations that respect "reduce motion"
 * The keyframes and the .m-* classes live in index.css.
 */
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { flushSync } from "react-dom";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/** Render while `open`, plus `exitMs` after it closes so the exit animation can play. */
export function usePresence(open: boolean, exitMs = 180): { mounted: boolean; closing: boolean } {
  const [mounted, setMounted] = useState(open);
  useEffect(() => {
    if (open) {
      setMounted(true);
      return;
    }
    const id = window.setTimeout(() => setMounted(false), prefersReducedMotion() ? 0 : exitMs);
    return () => window.clearTimeout(id);
  }, [open, exitMs]);
  return { mounted: open || mounted, closing: !open && mounted };
}

/**
 * Sliding highlight for a segmented control. Put `ref` on a `relative` container, give every option
 * `data-thumb-key={key}`, and render an absolutely positioned element with `style`.
 */
export function useSlidingThumb<T extends HTMLElement = HTMLDivElement>(active: string) {
  const ref = useRef<T | null>(null);
  const [style, setStyle] = useState<CSSProperties>({ opacity: 0 });
  const placed = useRef(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const btn = Array.from(el.querySelectorAll<HTMLElement>("[data-thumb-key]")).find((b) => b.dataset.thumbKey === active);
      if (!btn) {
        setStyle({ opacity: 0 });
        return;
      }
      setStyle({
        width: btn.offsetWidth,
        height: btn.offsetHeight,
        transform: `translate(${btn.offsetLeft}px, ${btn.offsetTop}px)`,
        opacity: 1,
        // the first placement must not slide in from the corner
        transition: placed.current ? undefined : "none",
      });
      placed.current = true;
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    el.querySelectorAll("[data-thumb-key]").forEach((b) => ro.observe(b));
    void document.fonts?.ready.then(measure);
    return () => ro.disconnect();
  }, [active]);
  return { ref, style };
}

/** A number that eases towards `value` (ease-out cubic). */
export function useTween(value: number, ms = 450): number {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  const current = useRef(value);
  useEffect(() => {
    if (prefersReducedMotion() || !Number.isFinite(value)) {
      current.current = value;
      setShown(value);
      return;
    }
    from.current = current.current;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const k = Math.min(1, (now - start) / ms);
      const v = from.current + (value - from.current) * (1 - (1 - k) ** 3);
      current.current = v;
      setShown(v);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return shown;
}

/** Web Animations API helper: no-op (resolves at once) when the user asked for reduced motion. */
export function animateEl(el: Element, keyframes: Keyframe[], options: KeyframeAnimationOptions): Animation | null {
  if (prefersReducedMotion() || typeof el.animate !== "function") return null;
  return el.animate(keyframes, options);
}

type DocWithVT = Document & { startViewTransition?: (cb: () => void) => unknown };

/** Cross-fade the whole page through a state change (theme, language); instant where unsupported. */
export function withViewTransition(update: () => void): void {
  const d = document as DocWithVT;
  if (!d.startViewTransition || prefersReducedMotion()) {
    update();
    return;
  }
  d.startViewTransition(() => flushSync(update));
}
