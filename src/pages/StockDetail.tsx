import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { track } from '../api/behaviour';
import type { AxiosInstance } from 'axios';
import { Bell } from 'lucide-react';
import PriceChart, { type Candle } from '../components/PriceChart/PriceChart';
import CandlestickChart from '../components/CandlestickChart/CandlestickChart';
import { Badge } from '../components/ui/Badge';
import { Card } from '../components/ui/Card';
import { CollapsibleZone } from '../components/ui/CollapsibleZone';
import { ExplainerPopover } from '../components/ui/ExplainerPopover';
import { FitScorecardContent } from '../components/ui/FitScorecardContent';
import { SectorComparisonContent } from '../components/ui/SectorComparisonContent';
import { Zone } from '../components/ui/Zone';
import { fetchSectorComparison, type SectorComparison } from '../api/sectorComparison';
import { useFitScores } from '../hooks/useFitScores';
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

// #90: static "what this means" copy for the Overview stats — every derived
// number gets one, raw Price doesn't (#87's selective-microcopy rule).
const STAT_EXPLANATIONS: Record<string, string> = {
  pe: 'Price divided by earnings per share — how many years of current earnings it takes to pay back the share price. Lower is cheaper relative to earnings.',
  marketCap: 'Total market value of all outstanding shares — price times shares issued.',
  pb: "Price divided by book (net asset) value per share — how the market prices the company relative to its accounting net worth.",
  dividendYield: 'Annual cash dividend as a percentage of the current share price.',
  epsGrowth: 'Year-over-year growth in earnings per share.',
  peg: 'P/E divided by EPS growth rate — a lower PEG can suggest growth priced more cheaply relative to how fast earnings are growing.',
  cashDiv: 'Cash dividend as a percentage of face value, for the given year.',
};

function Stat({ label, value, explanation }: { label: string; value: string; explanation?: string }) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-3">
      <div className="flex items-center gap-1 text-xs text-[var(--text-secondary)]">
        {label}
        {explanation && <ExplainerPopover label={`What does ${label} mean?`}>{explanation}</ExplainerPopover>}
      </div>
      <div className="text-lg font-semibold tabular-nums text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

// Inline price-alert setter (reconciled from main's StockProfile into the trunk
// StockDetail, #82) — seeds the target from the current price, POSTs /alerts.
// #90: a standalone action card, not one of the 5 named zones — it doesn't
// have a "reason" to explain, so it stays outside the zone/collapsible system
// and always visible (a primary action shouldn't hide behind a disclosure).
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
    <Card>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <Bell size={16} /> Set Price Alert
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="number"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="Target price"
          aria-label="Target price"
          className="border p-2 rounded tabular-nums"
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
    </Card>
  );
}

export default function StockDetail({ client }: { client: AxiosInstance }) {
  const { symbol = '' } = useParams();
  const [fund, setFund] = useState<Fundamentals | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [chart, setChart] = useState<'line' | 'candles'>('line');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sectorZoneOpen, setSectorZoneOpen] = useState(false);
  const [sectorComparison, setSectorComparison] = useState<SectorComparison | undefined>(undefined);
  const [sectorLoading, setSectorLoading] = useState(false);
  const fetchedSectorForRef = useRef<string | null>(null);
  const getFit = useFitScores(client, symbol ? [symbol] : []);

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

  // #92: lazy — only fetch when the (collapsed-by-default) Sector zone is
  // open, keyed on (symbol, open) rather than a one-shot flag. Re-opening the
  // same symbol's zone skips the refetch (fetchedSectorForRef still matches);
  // navigating to a different symbol while it's open refetches automatically,
  // since react-router reuses this component instance across a param change
  // rather than remounting it.
  useEffect(() => {
    if (!sectorZoneOpen || fetchedSectorForRef.current === symbol) return;
    fetchedSectorForRef.current = symbol;
    setSectorLoading(true);
    fetchSectorComparison(client, symbol)
      .then(setSectorComparison)
      .catch(() => {
        /* best-effort — the zone just stays in its loading/empty state */
      })
      .finally(() => setSectorLoading(false));
  }, [client, symbol, sectorZoneOpen]);

  if (loading) return <div className="text-center py-8">Loading {symbol}…</div>;
  if (error) return <p className="text-red-500 text-sm">{error}</p>;
  if (!fund) return null;

  const d = fund.derived;
  const ratios = Object.entries(fund.reported);
  const fit = getFit(fund.symbol);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">{fund.symbol}</h1>
        <Link to="/screener" className="text-sm text-[var(--accent-blue)] hover:underline">
          ← Screener
        </Link>
      </div>

      {/* #90: Fit-for-you leads the page — the personalization spine's
          headline differentiator, not just a header chip cluster. */}
      {fit && <FitScorecardContent fit={fit} revealIndex={0} />}

      <Card revealIndex={1}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Price" value={num(fund.price)} />
          <Stat label="P/E" value={num(fund.pe)} explanation={STAT_EXPLANATIONS.pe} />
          <Stat
            label="Market Cap (bn BDT)"
            value={num(fund.market_cap_bdt_bn)}
            explanation={STAT_EXPLANATIONS.marketCap}
          />
          <Stat label="P/B" value={num(d.price_to_book)} explanation={STAT_EXPLANATIONS.pb} />
          <Stat
            label="Dividend Yield %"
            value={num(d.dividend_yield_pct)}
            explanation={STAT_EXPLANATIONS.dividendYield}
          />
          <Stat
            label="EPS Growth %/yr"
            value={num(d.eps_growth_pct)}
            explanation={STAT_EXPLANATIONS.epsGrowth}
          />
          <Stat label="PEG" value={num(d.peg)} explanation={STAT_EXPLANATIONS.peg} />
          <Stat
            label={`Cash Div % (${d.dividend_year ?? '—'})`}
            value={num(d.cash_dividend_pct)}
            explanation={STAT_EXPLANATIONS.cashDiv}
          />
        </div>
      </Card>

      <SetPriceAlert client={client} symbol={fund.symbol} price={fund.price} />

      <Zone
        type="price"
        revealIndex={2}
        actions={
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
        }
      >
        {candles.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">No price history.</p>
        ) : chart === 'line' ? (
          <PriceChart symbol={fund.symbol} data={candles} />
        ) : (
          <CandlestickChart data={candles} />
        )}
      </Zone>

      <CollapsibleZone type="fundamentals" defaultOpen={false}>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-[var(--border-color)] text-sm">
            <thead>
              <tr className="text-left text-[var(--text-secondary)]">
                <th className="px-3 py-2">Metric</th>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2 text-right">Value</th>
                <th className="px-3 py-2 text-right">Year</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]">
              {ratios.map(([key, r]) => (
                <tr key={key}>
                  <td className="px-3 py-2 font-medium text-[var(--text-primary)]">
                    <span className="inline-flex items-center gap-1">
                      {r.reported_as}
                      <ExplainerPopover label={`What does ${r.reported_as} mean?`}>
                        {r.equation}
                      </ExplainerPopover>
                    </span>
                    {r.sign_inverted && (
                      <span className="ml-2 inline-flex items-center gap-1">
                        <Badge variant="warning">⚠ sign</Badge>
                        <ExplainerPopover label="Why this sign may be misleading">
                          Sign may be misleading — e.g. a loss over negative equity.
                        </ExplainerPopover>
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[var(--text-secondary)]">{r.category}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-[var(--text-primary)]">
                    {num(r.value, 4)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-[var(--text-secondary)]">
                    {r.year}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-6 overflow-x-auto">
          <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">EPS / NAV history</h3>
          <table className="min-w-full divide-y divide-[var(--border-color)] text-sm">
            <thead>
              <tr className="text-left text-[var(--text-secondary)]">
                <th className="px-3 py-2">Year</th>
                <th className="px-3 py-2 text-right">EPS</th>
                <th className="px-3 py-2 text-right">NAV</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]">
              {fund.eps_history.map((e) => (
                <tr key={e.year}>
                  <td className="px-3 py-2 tabular-nums text-[var(--text-primary)]">{e.year}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-[var(--text-primary)]">
                    {num(e.eps)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-[var(--text-primary)]">
                    {num(e.nav)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {fund.caveats && fund.caveats.length > 0 && (
          <ul className="mt-4 list-disc pl-5 text-xs text-[var(--text-secondary)]">
            {fund.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}
      </CollapsibleZone>

      <CollapsibleZone type="sector" defaultOpen={false} onOpenChange={setSectorZoneOpen}>
        <SectorComparisonContent
          data={sectorComparison?.symbol === fund.symbol ? sectorComparison : undefined}
          loading={sectorLoading}
        />
      </CollapsibleZone>
    </div>
  );
}
