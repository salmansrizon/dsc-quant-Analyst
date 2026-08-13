import { useState } from 'react';
import { track } from '../api/behaviour';
import type { AxiosInstance } from 'axios';
import { Link } from 'react-router-dom';
import { FitScorecard } from '../components/ui/FitScorecard';
import { useFitScores } from '../hooks/useFitScores';

interface Row {
  symbol: string;
  sector?: string | null;
  price?: number | null;
  volume?: number | null;
  market_cap?: number | null;
  pe?: number | null;
  pb?: number | null;
  dividend_yield?: number | null;
}

interface Filter {
  field: string;
  op: string;
  value: string;
}

const PRESETS = [
  { key: 'value', label: 'Value' },
  { key: 'growth', label: 'Growth' },
  { key: 'dividend_kings', label: 'Dividend Kings' },
];

const FIELDS = ['price', 'volume', 'market_cap', 'pe', 'pb', 'dividend_yield'];
const OPS = [
  { key: 'gt', label: '>' },
  { key: 'gte', label: '≥' },
  { key: 'lt', label: '<' },
  { key: 'lte', label: '≤' },
  { key: 'eq', label: '=' },
];

const num = (v?: number | null) => (v == null ? '—' : v.toFixed(2));

export default function Screener({ client }: { client: AxiosInstance }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [filters, setFilters] = useState<Filter[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fitScores = useFitScores(client, rows.map((r) => r.symbol));

  const body = (preset?: string) => ({
    preset,
    filters: preset
      ? undefined
      : filters
          .filter((f) => f.value !== '')
          .map((f) => ({ field: f.field, op: f.op, value: Number(f.value) })),
    limit: 200,
  });

  const run = (preset?: string) => {
    setLoading(true);
    setError(null);
    setNotice(null);
    setSelected(new Set());
    // #86: a screener run reveals the user's criteria.
    track({ event_type: 'screener_run', payload: body(preset) });
    client
      .post('/market/screener', body(preset))
      .then((res) => setRows(res.data.results))
      .catch((e) => setError(e?.response?.data?.detail ?? 'Screen failed'))
      .finally(() => setLoading(false));
  };

  const toggle = (symbol: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(symbol) ? next.delete(symbol) : next.add(symbol);
      return next;
    });
  };

  const addToWatchlist = () => {
    if (selected.size === 0) return;
    client
      .post('/market/screener/watchlist', { symbols: [...selected] })
      .then(() => setNotice(`Added ${selected.size} symbol(s) to your watchlist.`))
      .catch(() => setError('Failed to add to watchlist'));
  };

  const exportCsv = () => {
    client
      .post('/market/screener/export', body(undefined), { responseType: 'blob' })
      .then((res) => {
        const url = URL.createObjectURL(new Blob([res.data]));
        const a = document.createElement('a');
        a.href = url;
        a.download = 'screener_results.csv';
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => setError('Export failed'));
  };

  const addFilter = () =>
    setFilters((f) => [...f, { field: 'pe', op: 'lte', value: '' }]);
  const setFilter = (i: number, patch: Partial<Filter>) =>
    setFilters((f) => f.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const removeFilter = (i: number) =>
    setFilters((f) => f.filter((_, j) => j !== i));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Screener</h1>

      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => run(p.key)}
            className="px-3 py-2 rounded-md text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-700"
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-lg shadow-sm p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Custom filters</h2>
          <button
            type="button"
            onClick={addFilter}
            className="text-sm text-indigo-600 hover:underline"
          >
            + Add filter
          </button>
        </div>
        {filters.map((f, i) => (
          <div key={i} className="flex items-center gap-2">
            <select
              value={f.field}
              onChange={(e) => setFilter(i, { field: e.target.value })}
              className="border rounded px-2 py-1 text-sm"
            >
              {FIELDS.map((fl) => (
                <option key={fl} value={fl}>
                  {fl}
                </option>
              ))}
            </select>
            <select
              value={f.op}
              onChange={(e) => setFilter(i, { op: e.target.value })}
              className="border rounded px-2 py-1 text-sm"
            >
              {OPS.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
            <input
              type="number"
              value={f.value}
              onChange={(e) => setFilter(i, { value: e.target.value })}
              className="border rounded px-2 py-1 text-sm w-32"
              placeholder="value"
            />
            <button
              type="button"
              onClick={() => removeFilter(i)}
              className="text-red-500 text-sm"
            >
              ✕
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => run(undefined)}
          className="px-3 py-2 rounded-md text-sm font-medium bg-gray-800 text-white hover:bg-gray-900"
        >
          Run filters
        </button>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}
      {notice && <p className="text-green-600 text-sm">{notice}</p>}
      {loading && <p className="text-gray-500">Screening…</p>}

      {rows.length > 0 && (
        <>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">{rows.length} match(es)</span>
            <button
              type="button"
              onClick={addToWatchlist}
              disabled={selected.size === 0}
              className="px-3 py-1.5 rounded-md text-sm bg-indigo-600 text-white disabled:opacity-40"
            >
              Add {selected.size || ''} to watchlist
            </button>
            <button
              type="button"
              onClick={exportCsv}
              className="px-3 py-1.5 rounded-md text-sm border border-gray-300 hover:bg-gray-50"
            >
              Export CSV
            </button>
          </div>
          <div className="overflow-x-auto bg-white rounded-lg shadow-sm">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="px-3 py-2" />
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Fit</th>
                  <th className="px-3 py-2">Sector</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">Mkt Cap (bn)</th>
                  <th className="px-3 py-2 text-right">P/E</th>
                  <th className="px-3 py-2 text-right">P/B</th>
                  <th className="px-3 py-2 text-right">Div Yield %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((r) => (
                  <tr key={r.symbol} data-testid="screener-row">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(r.symbol)}
                        onChange={() => toggle(r.symbol)}
                        aria-label={`select ${r.symbol}`}
                      />
                    </td>
                    <td className="px-3 py-2 font-medium">
                      <Link to={`/stock/${r.symbol}`} className="text-indigo-600 hover:underline">
                        {r.symbol}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      <FitScorecard fit={fitScores[r.symbol.toUpperCase()]} />
                    </td>
                    <td className="px-3 py-2 text-gray-600">{r.sector ?? '—'}</td>
                    <td className="px-3 py-2 text-right">{num(r.price)}</td>
                    <td className="px-3 py-2 text-right">{num(r.market_cap)}</td>
                    <td className="px-3 py-2 text-right">{num(r.pe)}</td>
                    <td className="px-3 py-2 text-right">{num(r.pb)}</td>
                    <td className="px-3 py-2 text-right">{num(r.dividend_yield)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
