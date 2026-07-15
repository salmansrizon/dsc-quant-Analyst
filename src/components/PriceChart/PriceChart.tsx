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

  return (
    <div data-testid="price-chart" className="bg-white shadow p-4 rounded">
      <h3 className="text-lg font-semibold mb-2">{symbol}</h3>
      {series.length === 0 ? (
        <p className="text-gray-500 text-sm">No price data</p>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={series}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={24} />
            <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey="close" stroke="#4f46e5" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
