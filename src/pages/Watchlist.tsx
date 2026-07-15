import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import PriceChart from '../components/PriceChart/PriceChart';

interface WatchlistItem {
  id: string;
  symbol: string;
  LTP?: number;
  ChangePct?: number;
  Sector?: string;
}

export default function Watchlist({ client }: { client: AxiosInstance }) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [candles, setCandles] = useState<unknown[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client
      .get('/watchlist')
      .then((res) => setItems(res.data))
      .finally(() => setLoading(false));
  }, [client]);

  const handleSelect = (symbol: string) => {
    setSelected(symbol);
    client.get(`/market/price-history/${symbol}`).then((res) => setCandles(res.data));
  };

  if (loading) return <div className="text-center py-8">Loading watchlist…</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">My Watchlist</h1>

      {items.length === 0 ? (
        <p className="text-gray-500">Your watchlist is empty.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-2 text-left">Symbol</th>
                <th className="px-4 py-2 text-left">Sector</th>
                <th className="px-4 py-2 text-right">LTP</th>
                <th className="px-4 py-2 text-right">Change %</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {items.map((it) => (
                <tr key={it.id} data-testid="watchlist-row">
                  <td className="px-4 py-2 font-medium">{it.symbol}</td>
                  <td className="px-4 py-2 text-gray-600">{it.Sector ?? '—'}</td>
                  <td className="px-4 py-2 text-right">{it.LTP?.toFixed(2) ?? '—'}</td>
                  <td
                    className={`px-4 py-2 text-right ${
                      (it.ChangePct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {it.ChangePct?.toFixed(2) ?? '—'}%
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => handleSelect(it.symbol)}
                      className="text-indigo-600 hover:underline text-sm"
                    >
                      Chart
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && candles.length > 0 && (
        <PriceChart candles={candles as never[]} symbol={selected} />
      )}
    </div>
  );
}
