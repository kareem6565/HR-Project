import { useEffect, useRef, useState } from "react";

// Animates a number from 0 to `target` with an ease-out curve.
// Renders the final value immediately when animation is not possible
// (SSR/tests without matchMedia) or when the user prefers reduced motion,
// so assistive tech and tests always see the true value.
export function motionSafe() {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    typeof window.requestAnimationFrame === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export default function useCountUp(target, { duration = 1100 } = {}) {
  const numeric = typeof target === "number" && Number.isFinite(target);
  const [display, setDisplay] = useState(() =>
    numeric && motionSafe() ? 0 : target,
  );
  const frame = useRef(null);

  useEffect(() => {
    if (!numeric || !motionSafe()) {
      setDisplay(target);
      return undefined;
    }
    const t0 = performance.now();
    const tick = (t) => {
      const p = Math.min((t - t0) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(target * eased));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [target, duration, numeric]);

  return display;
}
