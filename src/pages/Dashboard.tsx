import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { Link } from 'react-router-dom';
import HomeFeed from '../components/HomeFeed/HomeFeed';
import MarketSummary from '../components/MarketSummary/DashboardSummary';
import PriceChange from '../components/PriceChange/PriceChange';
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
}: {
  title: string;
  rows: LeaderRow[];
  metricLabel?: string;
}) {
  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-400">No data yet.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {rows.map((r) => (
            <li key={r.Symbol} className="flex items-center justify-between py-2 text-sm">
              <Link to={`/stock/${r.Symbol}`} className="font-medium text-indigo-600 hover:underline">
                {r.Symbol}
              </Link>
              <span className="flex items-center gap-3">
                {r.LTP != null && <span className="text-gray-900">৳{Number(r.LTP).toFixed(2)}</span>}
                {metricLabel != null && r.MetricValue != null ? (
                  <span className="text-gray-700">
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
    </div>
  );
}

// Market breadth bar: gainers / losers / unchanged as proportional segments.
function StrengthBar({ strength }: { strength: Strength }) {
  const total = strength.Gainers + strength.Losers + strength.Unchanged || 1;
  const pct = (n: number) => `${(n / total) * 100}%`;
  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">Market Strength</h2>
      <div className="flex h-4 rounded overflow-hidden" aria-label="Market breadth">
        <div className="bg-green-500" style={{ width: pct(strength.Gainers) }} title={`${strength.Gainers} up`} />
        <div className="bg-gray-300" style={{ width: pct(strength.Unchanged) }} title={`${strength.Unchanged} flat`} />
        <div className="bg-red-500" style={{ width: pct(strength.Losers) }} title={`${strength.Losers} down`} />
      </div>
      <div className="flex justify-between mt-2 text-xs text-gray-600">
        <span className="text-green-600">{strength.Gainers} up</span>
        <span>{strength.Unchanged} flat</span>
        <span className="text-red-600">{strength.Losers} down</span>
      </div>
    </div>
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
      <h1 className="text-2xl font-bold">Market Dashboard</h1>
      {error && <p className="text-red-500 text-sm">{error}</p>}

      {/* #96: the personalized 'for you' surface leads the Dashboard — same
          precedence as Stock Detail's Fit zone (#90). No-ops (renders null)
          for a logged-out visitor. */}
      <HomeFeed client={client} />

      <div className="grid md:grid-cols-2 gap-6">
        <MarketSummary client={client} />
        {strength && <StrengthBar strength={strength} />}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <LeaderTable title="Top by Traded Value" rows={value} />
        <LeaderTable title="Top Gainers" rows={gainers} />
      </div>

      {peLow.length > 0 && (
        <div className="grid md:grid-cols-2 gap-6">
          <LeaderTable title="Lowest P/E" rows={peLow} metricLabel="PE" />
        </div>
      )}
    </div>
  );
}
