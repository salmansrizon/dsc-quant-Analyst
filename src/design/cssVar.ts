// Resolves a CSS custom property to its live value — used wherever a canvas or
// SVG chart needs a literal color string instead of a var() reference (which
// canvas can't consume, and Recharts' SVG props don't resolve at paint time
// the way CSS does). Shared by CandlestickChart (#87) and PriceChart (#90).
export function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}
