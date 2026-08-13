import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { track } from '../api/behaviour';
import type { AxiosInstance } from 'axios';
import { Bell } from 'lucide-react';
import PriceChart, { type Candle } from '../components/PriceChart/PriceChart';
import CandlestickChart from '../components/CandlestickChart/CandlestickChart';
import { Badge } from '../components/ui/Badge';
import { ExplainerPopover } from '../components/ui/ExplainerPopover';
import { errorMessage } from '../api/errorMessage';
import { useToast } from '../context/ToastContext';

interface Ratio {
  value: number | null;
  reported_as: string;
  category: string;
  year: number;
  equation: string;
  sign_inverted: boolean | null;
}

interface Fundamentals {
  symbol: string;
  price?: number | null;
  market_cap_bdt_bn?: number | null;
  pe?: number | null;
  reported: Record<string, Ratio>;
  derived: {
    price_to_book?: number | null;
    dividend_yield_pct?: number | null;
    dividend_year?: number | null;
    cash_dividend_pct?: number | null;
    eps_growth_pct?: number | null;
    peg?: number | null;
  };
  eps_history: { year: number; eps: number | null; nav: number | null }[];
  caveats?: string[];
}

const num = (v?: number | null, d = 2) => (v == null ? '—' : v.toFixed(d));

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-lg shadow-sm px-4 py-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

// Inline price-alert setter (reconciled from main's StockProfile into the trunk
// StockDetail, #82) — seeds the target from the current price, POSTs /alerts.
function SetPriceAlert({
  client,
  symbol,
  price,
}: {
  client: AxiosInstance;
  symbol: string;
  price?: number | null;
}) {
  const toast = useToast();
  const [target, setTarget] = useState(price != null ? String(price) : '');
  const [direction, setDirection] = useState<'above' | 'below'>('above');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    const value = Number(target);
    if (!value || value <= 0) {
      toast.error('Enter a valid target price');
      return;
    }
    setSaving(true);
    try {
      await client.post('/alerts', { symbol, target_price: value, direction });
      toast.success(`Alert set for ${symbol} ${direction} ৳${value.toFixed(2)}`);
    } catch (err) {
      toast.error(errorMessage(err, 'Failed to set alert'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm p-4">
      <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <Bell size={16} /> Set Price Alert
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="number"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="Target price"
          aria-label="Target price"
          className="border p-2 rounded"
        />
        <select
          value={direction}
          onChange={(e) => setDirection(e.target.value as 'above' | 'below')}
          aria-label="Direction"
          className="border p-2 rounded"
        >
          <option value="above">Above</option>
          <option value="below">Below</option>
        </select>
        <button type="button" onClick={submit} disabled={saving} className="btn-primary">
          {saving ? 'Setting…' : 'Set Alert'}
        </button>
      </div>
    </div>
  );
}

export default function StockDetail({ client }: { client: AxiosInstance }) {
  const { symbol = '' } = useParams();
  const [fund, setFund] = useState<Fundamentals | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [chart, setChart] = useState<'line' | 'candles'>('line');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      client.get(`/market/fundamentals/${symbol}`),
      client.get(`/market/price-history/${symbol}`).catch(() => ({ data: [] })),
    ])
      .then(([f, h]) => {
        setFund(f.data);
        setCandles(h.data);
        // #86: a stock-detail visit — the core interest signal. Carries the
        // stock's sector so it feeds sector affinity too.
        track({ event_type: 'view', symbol, sector: f.data?.sector });
      })
      .catch(() => setError(`Failed to load ${symbol}`))
      .finally(() => setLoading(false));
  }, [client, symbol]);

  if (loading) return <div className="text-center py-8">Loading {symbol}…</div>;
  if (error) return <p className="text-red-500 text-sm">{error}</p>;
  if (!fund) return null;

  const d = fund.derived;
  const ratios = Object.entries(fund.reported);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{fund.symbol}</h1>
        <Link to="/screener" className="text-sm text-indigo-600 hover:underline">
          ← Screener
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Price" value={num(fund.price)} />
        <Stat label="P/E" value={num(fund.pe)} />
        <Stat label="Market Cap (bn BDT)" value={num(fund.market_cap_bdt_bn)} />
        <Stat label="P/B" value={num(d.price_to_book)} />
        <Stat label="Dividend Yield %" value={num(d.dividend_yield_pct)} />
        <Stat label="EPS Growth %/yr" value={num(d.eps_growth_pct)} />
        <Stat label="PEG" value={num(d.peg)} />
        <Stat
          label={`Cash Div % (${d.dividend_year ?? '—'})`}
          value={num(d.cash_dividend_pct)}
        />
      </div>

      <SetPriceAlert client={client} symbol={fund.symbol} price={fund.price} />

      <div className="bg-white rounded-lg shadow-sm p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-700">Price history</h2>
          <div className="flex gap-2" role="group" aria-label="Chart type">
            {(['line', 'candles'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setChart(t)}
                aria-pressed={chart === t}
                className="btn-secondary text-xs"
                style={{ padding: '4px 10px', opacity: chart === t ? 1 : 0.6 }}
              >
                {t === 'line' ? 'Line' : 'Candles'}
              </button>
            ))}
          </div>
        </div>
        {candles.length === 0 ? (
          <p className="text-gray-500 text-sm">No price history.</p>
        ) : chart === 'line' ? (
          <PriceChart symbol={fund.symbol} data={candles} />
        ) : (
          <CandlestickChart data={candles} />
        )}
      </div>

      <div className="bg-white rounded-lg shadow-sm p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Reported ratios</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="px-3 py-2">Metric</th>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2 text-right">Value</th>
                <th className="px-3 py-2 text-right">Year</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {ratios.map(([key, r]) => (
                <tr key={key}>
                  <td className="px-3 py-2 font-medium">
                    {r.reported_as}
                    {r.sign_inverted && (
                      <span className="ml-2 inline-flex items-center gap-1">
                        <Badge variant="warning">⚠ sign</Badge>
                        <ExplainerPopover label="Why this sign may be misleading">
                          Sign may be misleading — e.g. a loss over negative equity.
                        </ExplainerPopover>
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-600">{r.category}</td>
                  <td className="px-3 py-2 text-right">{num(r.value, 4)}</td>
                  <td className="px-3 py-2 text-right">{r.year}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-2">EPS / NAV history</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="px-3 py-2">Year</th>
                <th className="px-3 py-2 text-right">EPS</th>
                <th className="px-3 py-2 text-right">NAV</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {fund.eps_history.map((e) => (
                <tr key={e.year}>
                  <td className="px-3 py-2">{e.year}</td>
                  <td className="px-3 py-2 text-right">{num(e.eps)}</td>
                  <td className="px-3 py-2 text-right">{num(e.nav)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {fund.caveats && fund.caveats.length > 0 && (
        <ul className="text-xs text-gray-500 list-disc pl-5">
          {fund.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
