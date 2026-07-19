import { TrendingDown, TrendingUp } from 'lucide-react';

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
  if (pct == null) return null;
  const value = Number(pct);
  const isUp = value >= 0;
  return (
    <span className={`flex items-center gap-1 ${isUp ? 'text-green-600' : 'text-red-600'}`}>
      {isUp ? <TrendingUp size={size} /> : <TrendingDown size={size} />}
      {isUp ? '+' : ''}
      {value.toFixed(2)}%
    </span>
  );
}
