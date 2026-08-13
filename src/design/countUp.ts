// Pure interpolation for the price/number count-up micro-interaction (#87).
// Kept free of rAF/DOM so it's cheap to unit test; src/hooks/useCountUp.ts
// wraps this with requestAnimationFrame for actual use.
export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export function interpolateCountUp(from: number, to: number, progress: number): number {
  const t = Math.min(Math.max(progress, 0), 1);
  return from + (to - from) * easeOutCubic(t);
}
