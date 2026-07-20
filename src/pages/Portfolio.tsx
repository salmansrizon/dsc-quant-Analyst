import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import PortfolioHealth, { type Health } from '../components/PortfolioHealth/PortfolioHealth';

interface Holding {
  id: string;
  symbol: string;
  quantity: number;
  buy_price: number;
  current_price?: number;
  pnl?: number;
  pnl_percent?: number;
}

interface Summary {
  total_holdings?: number;
  total_invested?: number;
  current_value?: number;
  total_pnl?: number;
  avg_pnl_pct?: number;
  health?: Health;
}

const money = (n?: number) => (typeof n === 'number' ? n.toFixed(2) : '—');

export default function Portfolio({ client }: { client: AxiosInstance }) {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [summary, setSummary] = useState<Summary>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([client.get('/portfolio'), client.get('/portfolio/summary')])
      .then(([h, s]) => {
        setHoldings(h.data);
        setSummary(s.data ?? {});
      })
      .finally(() => setLoading(false));
  }, [client]);

  if (loading) return <div className="text-center py-8">Loading portfolio…</div>;

  const totalPnl = summary.total_pnl ?? 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">My Portfolio</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
        <div>
          <h2 className="text-sm text-gray-600">Total Invested</h2>
          <p className="text-xl font-semibold">{money(summary.total_invested)}</p>
        </div>
        <div>
          <h2 className="text-sm text-gray-600">Current Value</h2>
          <p className="text-xl font-semibold">{money(summary.current_value)}</p>
        </div>
        <div>
          <h2 className="text-sm text-gray-600">Total P&amp;L</h2>
          <p className={`text-xl font-semibold ${totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {money(summary.total_pnl)} ({money(summary.avg_pnl_pct)}%)
          </p>
        </div>
      </div>

      <PortfolioHealth health={summary.health} />

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-2 text-left">Symbol</th>
              <th className="px-4 py-2 text-right">Qty</th>
              <th className="px-4 py-2 text-right">Buy Price</th>
              <th className="px-4 py-2 text-right">Current</th>
              <th className="px-4 py-2 text-right">P&amp;L</th>
              <th className="px-4 py-2 text-right">P&amp;L %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {holdings.map((h) => (
              <tr key={h.id} data-testid="portfolio-row">
                <td className="px-4 py-2 font-medium">{h.symbol}</td>
                <td className="px-4 py-2 text-right">{h.quantity}</td>
                <td className="px-4 py-2 text-right">{money(h.buy_price)}</td>
                <td className="px-4 py-2 text-right">{money(h.current_price)}</td>
                <td className={`px-4 py-2 text-right ${(h.pnl ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {money(h.pnl)}
                </td>
                <td className={`px-4 py-2 text-right ${(h.pnl_percent ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {money(h.pnl_percent)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
