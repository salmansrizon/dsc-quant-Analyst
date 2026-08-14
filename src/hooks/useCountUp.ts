import { useEffect, useRef, useState } from 'react';
import { interpolateCountUp } from '../design/countUp';

const DEFAULT_DURATION_MS = 400;

// #87: animates a displayed number toward `value` on change (live price
// ticks, fit scores). Skips the animation on first mount so tables don't
// count up from zero on initial load.
export function useCountUp(value: number, durationMs = DEFAULT_DURATION_MS): number {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const mountedRef = useRef(false);

  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      fromRef.current = value;
      return;
    }

    const from = fromRef.current;
    if (from === value) return;

    let startTimestamp: number | null = null;
    let rafId: number;

    function tick(timestamp: number) {
      if (startTimestamp === null) startTimestamp = timestamp;
      const elapsed = timestamp - startTimestamp;
      const progress = durationMs === 0 ? 1 : elapsed / durationMs;
      setDisplay(interpolateCountUp(from, value, progress));
      if (progress < 1) {
        rafId = requestAnimationFrame(tick);
      } else {
        fromRef.current = value;
      }
    }

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [value, durationMs]);

  return display;
}
