import { TrendingDown, TrendingUp } from 'lucide-react';
import { useCountUp } from '../../hooks/useCountUp';

// The colored ±pct% with an up/down arrow — one render shared by the Dashboard
// leaderboards and the SymbolSearch suggestion rows. Renders nothing when the
// change is unknown.
export default function PriceChange({
  pct,
  size = 14,
}: {
  pct?: number | null;
  size?: number;
}) {
  const value = pct == null ? null : Number(pct);
  // #87: price-number count-up. Hook is called unconditionally (Rules of
  // Hooks) with a 0 fallback while `value` is unknown; the early return below
  // means that fallback is never actually rendered.
  const animated = useCountUp(value ?? 0);
  if (value == null) return null;
  const isUp = value >= 0;
  return (
    <span className={`flex items-center gap-1 ${isUp ? 'text-green-600' : 'text-red-600'}`}>
      {isUp ? <TrendingUp size={size} /> : <TrendingDown size={size} />}
      {isUp ? '+' : ''}
      {animated.toFixed(2)}%
    </span>
  );
}
