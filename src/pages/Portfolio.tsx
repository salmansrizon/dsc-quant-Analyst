import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { HeartPulse } from 'lucide-react';
import PriceChange from '../components/PriceChange/PriceChange';
import { Card } from '../components/ui/Card';
import { VARIANT_COLOR_VAR } from '../components/ui/Badge';
import { FitScorecard } from '../components/ui/FitScorecard';
import { PortfolioHealthContent } from '../components/ui/PortfolioHealthContent';
import { useFitScores } from '../hooks/useFitScores';
import { fetchPortfolioHealth, type PortfolioHealth } from '../api/portfolioHealth';

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
}

const money = (n?: number) => (typeof n === 'number' ? n.toFixed(2) : '—');

export default function Portfolio({ client }: { client: AxiosInstance }) {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [summary, setSummary] = useState<Summary>({});
  const [health, setHealth] = useState<PortfolioHealth | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const getFit = useFitScores(client, holdings.map((h) => h.symbol));

  useEffect(() => {
    Promise.all([client.get('/portfolio'), client.get('/portfolio/summary')])
      .then(([h, s]) => {
        setHoldings(h.data);
        setSummary(s.data ?? {});
      })
      .finally(() => setLoading(false));
    // Best-effort, independent of the holdings/summary load — a failure here
    // just means the health card doesn't render, not a broken page (#97).
    fetchPortfolioHealth(client).then(setHealth).catch(() => {});
  }, [client]);

  if (loading) {
    return <div className="py-8 text-center text-[var(--text-secondary)]">Loading portfolio…</div>;
  }

  const totalPnl = summary.total_pnl ?? 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-[var(--text-primary)]">My Portfolio</h1>

      {/* #97: leads the page, same precedence as Stock Detail's Fit zone (#90)
          and the Dashboard feed (#96) — wires up #91's previously-unrendered
          portfolio-health seam. */}
      {health && (
        <Card revealIndex={0}>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
            <HeartPulse size={16} /> Portfolio Health
          </h2>
          <PortfolioHealthContent health={health} />
        </Card>
      )}

      <Card revealIndex={1}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <h2 className="text-sm text-[var(--text-secondary)]">Total Invested</h2>
            <p className="text-xl font-semibold tabular-nums text-[var(--text-primary)]">
              {money(summary.total_invested)}
            </p>
          </div>
          <div>
            <h2 className="text-sm text-[var(--text-secondary)]">Current Value</h2>
            <p className="text-xl font-semibold tabular-nums text-[var(--text-primary)]">
              {money(summary.current_value)}
            </p>
          </div>
          <div>
            <h2 className="text-sm text-[var(--text-secondary)]">Total P&amp;L</h2>
            <p
              className="text-xl font-semibold tabular-nums"
              style={{ color: totalPnl >= 0 ? VARIANT_COLOR_VAR.positive : VARIANT_COLOR_VAR.negative }}
            >
              {money(summary.total_pnl)} ({money(summary.avg_pnl_pct)}%)
            </p>
          </div>
        </div>
      </Card>

      <Card revealIndex={2}>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border-color)] text-sm">
            <thead>
              <tr className="text-left text-[var(--text-secondary)]">
                <th className="px-4 py-2">Symbol</th>
                <th className="px-4 py-2">Fit</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Buy Price</th>
                <th className="px-4 py-2 text-right">Current</th>
                <th className="px-4 py-2 text-right">P&amp;L</th>
                <th className="px-4 py-2 text-right">P&amp;L %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]">
              {holdings.map((h) => (
                <tr key={h.id} data-testid="portfolio-row">
                  <td className="px-4 py-2 font-medium text-[var(--text-primary)]">{h.symbol}</td>
                  <td className="px-4 py-2">
                    <FitScorecard fit={getFit(h.symbol)} />
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[var(--text-primary)]">
                    {h.quantity}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[var(--text-primary)]">
                    {money(h.buy_price)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[var(--text-primary)]">
                    {money(h.current_price)}
                  </td>
                  <td
                    className="px-4 py-2 text-right tabular-nums"
                    style={{ color: (h.pnl ?? 0) >= 0 ? VARIANT_COLOR_VAR.positive : VARIANT_COLOR_VAR.negative }}
                  >
                    {money(h.pnl)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    <PriceChange pct={h.pnl_percent} size={12} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
