import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { Link } from 'react-router-dom';
import { TrendingDown, TrendingUp } from 'lucide-react';
import MarketSummary from '../components/MarketSummary/DashboardSummary';
import { errorMessage } from '../api/errorMessage';

interface DashboardProps {
  client: AxiosInstance;
}

interface Strength {
  Gainers: number;
  Losers: number;
  Unchanged: number;
}

interface LeaderRow {
  Symbol: string;
  Sector?: string;
  LTP?: number;
  ChangePct?: number;
  Value?: number;
}

// Compact top-N table, reused by the leaderboard widgets (PRD-12, #82).
function LeaderTable({ title, rows }: { title: string; rows: LeaderRow[] }) {
  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">{title}</h2>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-400">No data yet.</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {rows.map((r) => {
            const pct = r.ChangePct != null ? Number(r.ChangePct) : null;
            const isUp = pct != null && pct >= 0;
            return (
              <li key={r.Symbol} className="flex items-center justify-between py-2 text-sm">
                <Link to={`/stock/${r.Symbol}`} className="font-medium text-indigo-600 hover:underline">
                  {r.Symbol}
                </Link>
                <span className="flex items-center gap-3">
                  {r.LTP != null && <span className="text-gray-900">৳{Number(r.LTP).toFixed(2)}</span>}
                  {pct != null && (
                    <span className={`flex items-center gap-1 ${isUp ? 'text-green-600' : 'text-red-600'}`}>
                      {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                      {isUp ? '+' : ''}
                      {pct.toFixed(2)}%
                    </span>
                  )}
                </span>
              </li>
            );
          })}
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      client.get('/market/strength'),
      client.get('/market/leaderboard?metric=value&limit=5'),
      client.get('/market/leaderboard?metric=gainer&limit=5'),
    ])
      .then(([s, v, g]) => {
        setStrength(s.data);
        setValue(Array.isArray(v.data) ? v.data : []);
        setGainers(Array.isArray(g.data) ? g.data : []);
      })
      .catch((err) => setError(errorMessage(err, 'Failed to load dashboard')));
  }, [client]);

  return (
    <div data-testid="dashboard-container" className="min-h-96 space-y-6">
      <h1 className="text-2xl font-bold">Market Dashboard</h1>
      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="grid md:grid-cols-2 gap-6">
        <MarketSummary client={client} />
        {strength && <StrengthBar strength={strength} />}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <LeaderTable title="Top by Traded Value" rows={value} />
        <LeaderTable title="Top Gainers" rows={gainers} />
      </div>
    </div>
  );
}
