import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { Link } from 'react-router-dom';
import HomeFeed from '../components/HomeFeed/HomeFeed';
import MarketSummary from '../components/MarketSummary/DashboardSummary';
import PriceChange from '../components/PriceChange/PriceChange';
import { Card } from '../components/ui/Card';
import { VARIANT_COLOR_VAR } from '../components/ui/Badge';
import { errorMessage } from '../api/errorMessage';
import type { MarketRow as LeaderRow } from '../api/marketTypes';

interface DashboardProps {
  client: AxiosInstance;
}

interface Strength {
  Gainers: number;
  Losers: number;
  Unchanged: number;
}

// Compact top-N table, reused by the leaderboard widgets (PRD-12, #82). With
// `metricLabel` set it shows the row's MetricValue (extremes) instead of the
// day's change %.
function LeaderTable({
  title,
  rows,
  metricLabel,
  revealIndex,
}: {
  title: string;
  rows: LeaderRow[];
  metricLabel?: string;
  revealIndex?: number;
}) {
  return (
    <Card revealIndex={revealIndex}>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">No data yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--border-color)]">
          {rows.map((r) => (
            <li key={r.Symbol} className="flex items-center justify-between py-2 text-sm">
              <Link
                to={`/stock/${r.Symbol}`}
                className="font-medium text-[var(--accent-blue)] hover:underline"
              >
                {r.Symbol}
              </Link>
              <span className="flex items-center gap-3">
                {r.LTP != null && (
                  <span className="tabular-nums text-[var(--text-primary)]">
                    ৳{Number(r.LTP).toFixed(2)}
                  </span>
                )}
                {metricLabel != null && r.MetricValue != null ? (
                  <span className="tabular-nums text-[var(--text-secondary)]">
                    {metricLabel} {Number(r.MetricValue).toFixed(2)}
                  </span>
                ) : (
                  <PriceChange pct={r.ChangePct} />
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// Market breadth bar: gainers / losers / unchanged as proportional segments.
function StrengthBar({ strength, revealIndex }: { strength: Strength; revealIndex?: number }) {
  const total = strength.Gainers + strength.Losers + strength.Unchanged || 1;
  const pct = (n: number) => `${(n / total) * 100}%`;
  return (
    <Card revealIndex={revealIndex}>
      <h2 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">Market Strength</h2>
      <div className="flex h-4 overflow-hidden rounded" aria-label="Market breadth">
        <div
          style={{ width: pct(strength.Gainers), background: VARIANT_COLOR_VAR.positive }}
          title={`${strength.Gainers} up`}
        />
        <div
          style={{ width: pct(strength.Unchanged), background: 'var(--border-color)' }}
          title={`${strength.Unchanged} flat`}
        />
        <div
          style={{ width: pct(strength.Losers), background: VARIANT_COLOR_VAR.negative }}
          title={`${strength.Losers} down`}
        />
      </div>
      <div className="mt-2 flex justify-between text-xs tabular-nums text-[var(--text-secondary)]">
        <span style={{ color: VARIANT_COLOR_VAR.positive }}>{strength.Gainers} up</span>
        <span>{strength.Unchanged} flat</span>
        <span style={{ color: VARIANT_COLOR_VAR.negative }}>{strength.Losers} down</span>
      </div>
    </Card>
  );
}

export default function Dashboard({ client }: DashboardProps) {
  const [strength, setStrength] = useState<Strength | null>(null);
  const [value, setValue] = useState<LeaderRow[]>([]);
  const [gainers, setGainers] = useState<LeaderRow[]>([]);
  const [peLow, setPeLow] = useState<LeaderRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Independent fetches: the extremes endpoints 5xx until dataGrid re-scrapes
    // the Audited_PE/NAV columns (#82), so a failure there must not blank out the
    // widgets that read pre-existing columns. Each swallows its own error.
    const load = <T,>(url: string, set: (v: T) => void, fallback: T) =>
      client.get(url).then((r) => set(r.data as T)).catch(() => set(fallback));

    Promise.all([
      load('/market/strength', setStrength, null as Strength | null),
      load('/market/leaderboard?metric=value&limit=5', setValue, [] as LeaderRow[]),
      load('/market/leaderboard?metric=gainer&limit=5', setGainers, [] as LeaderRow[]),
    ]).catch((err) => setError(errorMessage(err, 'Failed to load dashboard')));

    // Best-effort — hidden entirely if the columns aren't scraped yet.
    load('/market/extremes?metric=pe_low&limit=5', setPeLow, [] as LeaderRow[]);
  }, [client]);

  return (
    <div data-testid="dashboard-container" className="min-h-96 space-y-6">
      <h1 className="text-2xl font-bold text-[var(--text-primary)]">Market Dashboard</h1>
      {error && <p className="text-sm" style={{ color: VARIANT_COLOR_VAR.negative }}>{error}</p>}

      {/* #96: the personalized 'for you' surface leads the Dashboard — same
          precedence as Stock Detail's Fit zone (#90). No-ops (renders null)
          for a logged-out visitor. */}
      <HomeFeed client={client} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card revealIndex={0}>
          <MarketSummary client={client} />
        </Card>
        {strength && <StrengthBar strength={strength} revealIndex={1} />}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <LeaderTable title="Top by Traded Value" rows={value} revealIndex={2} />
        <LeaderTable title="Top Gainers" rows={gainers} revealIndex={3} />
      </div>

      {peLow.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2">
          <LeaderTable title="Lowest P/E" rows={peLow} metricLabel="PE" revealIndex={4} />
        </div>
      )}
    </div>
  );
}
