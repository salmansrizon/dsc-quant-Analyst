import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import PriceChart, { type Candle } from '../components/PriceChart/PriceChart';
import PriceChange from '../components/PriceChange/PriceChange';
import { Card } from '../components/ui/Card';
import { VARIANT_COLOR_VAR } from '../components/ui/Badge';
import { FitScorecard } from '../components/ui/FitScorecard';
import { useFitScores } from '../hooks/useFitScores';

interface WatchlistItem {
  id: string;
  symbol: string;
  LTP?: number;
  ChangePct?: number;
  Sector?: string;
}

export default function Watchlist({ client }: { client: AxiosInstance }) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const getFit = useFitScores(client, items.map((it) => it.symbol));

  useEffect(() => {
    client
      .get('/watchlist')
      .then((res) => setItems(res.data))
      .catch(() => setError('Failed to load watchlist'))
      .finally(() => setLoading(false));
  }, [client]);

  const handleSelect = (symbol: string) => {
    setSelected(symbol);
    setCandles([]);
    client
      .get(`/market/price-history/${symbol}`)
      .then((res) => setCandles(res.data))
      .catch(() => setError(`Failed to load history for ${symbol}`));
  };

  if (loading) {
    return <div className="py-8 text-center text-[var(--text-secondary)]">Loading watchlist…</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-[var(--text-primary)]">My Watchlist</h1>
      {error && <p className="text-sm" style={{ color: VARIANT_COLOR_VAR.negative }}>{error}</p>}

      {items.length === 0 ? (
        <p className="text-[var(--text-secondary)]">Your watchlist is empty.</p>
      ) : (
        <Card revealIndex={0}>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--border-color)] text-sm">
              <thead>
                <tr className="text-left text-[var(--text-secondary)]">
                  <th className="px-4 py-2">Symbol</th>
                  <th className="px-4 py-2">Fit</th>
                  <th className="px-4 py-2">Sector</th>
                  <th className="px-4 py-2 text-right">LTP</th>
                  <th className="px-4 py-2 text-right">Change %</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]">
                {items.map((it) => (
                  <tr key={it.id} data-testid="watchlist-row">
                    <td className="px-4 py-2 font-medium text-[var(--text-primary)]">{it.symbol}</td>
                    <td className="px-4 py-2">
                      <FitScorecard fit={getFit(it.symbol)} />
                    </td>
                    <td className="px-4 py-2 text-[var(--text-secondary)]">{it.Sector ?? '—'}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-[var(--text-primary)]">
                      {it.LTP?.toFixed(2) ?? '—'}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      <PriceChange pct={it.ChangePct} />
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => handleSelect(it.symbol)}
                        className="text-sm text-[var(--accent-blue)] hover:underline"
                      >
                        Chart
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {selected && candles.length > 0 && (
        <Card revealIndex={1}>
          <PriceChart candles={candles} symbol={selected} />
        </Card>
      )}
    </div>
  );
}
