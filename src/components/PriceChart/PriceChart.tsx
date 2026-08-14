import { useMemo } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { cssVar } from '../../design/cssVar';

export interface Candle {
  date?: string;
  Date?: string;
  open?: number;
  close?: number;
  Close?: number;
  LTP?: number;
  high?: number;
  low?: number;
}

interface PriceChartProps {
  symbol: string;
  /** Preferred prop. `candles` is accepted as an alias for legacy callers. */
  data?: Candle[];
  candles?: Candle[];
}

function pickClose(c: Candle): number {
  return c.close ?? c.Close ?? c.LTP ?? 0;
}

function pickDate(c: Candle): string {
  return c.date ?? c.Date ?? '';
}

export default function PriceChart({ symbol, data, candles }: PriceChartProps) {
  const rows = data ?? candles ?? [];
  const series = useMemo(
    () => rows.map((c) => ({ date: pickDate(c), close: pickClose(c) })),
    [rows],
  );

  // #90: theme-aware now that its parent zone is dark by default (#87) — was
  // left as a literal-white card until the surrounding page was dark enough
  // for the mismatch to actually show. Resolved live (not var()) since
  // Recharts' SVG props don't follow CSS custom properties at paint time.
  const gridColor = cssVar('--border-color', '#2b303c');
  const textColor = cssVar('--text-secondary', '#9aa1ad');
  const lineColor = cssVar('--accent-blue', '#3b82f6');

  return (
    <div data-testid="price-chart">
      <h3 className="mb-2 text-lg font-semibold text-[var(--text-primary)]">{symbol}</h3>
      {series.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">No price data</p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={series}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: textColor }} minTickGap={24} stroke={gridColor} />
            <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11, fill: textColor }} stroke={gridColor} />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                color: 'var(--text-primary)',
              }}
              labelStyle={{ color: 'var(--text-secondary)' }}
            />
            <Line type="monotone" dataKey="close" stroke={lineColor} dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
