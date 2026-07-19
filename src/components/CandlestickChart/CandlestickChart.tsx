import { useMemo } from 'react';
import {
  Bar,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Candle } from '../PriceChart/PriceChart';

interface OHLC {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

// price-history rows come capitalized (Date/High/Low/Open/Close); some callers
// pass the lowercase Candle shape. Normalize both, like PriceChart's pickers.
function toOHLC(c: Candle): OHLC {
  const anyC = c as Record<string, number | string | undefined>;
  const close = (anyC.close ?? anyC.Close ?? anyC.LTP ?? 0) as number;
  const open = (anyC.open ?? anyC.Open ?? close) as number;
  const high = (anyC.high ?? anyC.High ?? Math.max(open, close)) as number;
  const low = (anyC.low ?? anyC.Low ?? Math.min(open, close)) as number;
  const date = (anyC.date ?? anyC.Date ?? '') as string;
  return { date, open, high, low, close };
}

// Recharts renders one Bar spanning [low, high]; this shape paints the wick +
// the open→close body, green up / red down, off the theme CSS variables.
function CandleShape(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: OHLC;
}) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props;
  if (!payload) return null;
  const { open, close, high, low } = payload;
  const isUp = close >= open;
  const color = isUp ? 'var(--accent-green)' : 'var(--accent-red)';
  const range = high - low || 1;
  const bodyTop = y + (height * (high - Math.max(open, close))) / range;
  const bodyBottom = y + (height * (high - Math.min(open, close))) / range;
  const bodyHeight = Math.max(bodyBottom - bodyTop, 1);
  const cx = x + width / 2;
  return (
    <g>
      <line x1={cx} x2={cx} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={x} y={bodyTop} width={width} height={bodyHeight} fill={color} />
    </g>
  );
}

export default function CandlestickChart({ data }: { data: Candle[] }) {
  const series = useMemo(() => data.map(toOHLC), [data]);
  return (
    <div data-testid="candlestick-chart" style={{ height: 300 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={series}>
          <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={24} axisLine={false} tickLine={false} />
          <YAxis domain={['dataMin', 'dataMax']} tick={{ fontSize: 11 }} width={48} axisLine={false} tickLine={false} />
          <Tooltip />
          <Bar dataKey={(d: OHLC) => [d.low, d.high]} shape={CandleShape as never} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
