import React from 'react';
import { ComposedChart, Bar, Line, XAxis, YAxis, ResponsiveContainer, BarChart, Tooltip } from 'recharts';
import { colors } from '../design';

const EMA_LINES = [
  ['EMA20', '#60a5fa'], ['EMA50', '#f59e0b'], ['EMA100', '#a78bfa'], ['EMA200', '#f472b6'],
];

const Candle = (props) => {
  const { x, y, width, height, payload } = props;
  const { open, close, high, low } = payload;
  const isUp = close >= open;
  const color = isUp ? 'var(--color-green)' : 'var(--color-red)';
  const range = high - low || 1;
  const bodyTop = y + (height * (high - Math.max(open, close))) / range;
  const bodyBottom = y + (height * (high - Math.min(open, close))) / range;
  const bodyHeight = Math.max(bodyBottom - bodyTop, 1);
  const cx = x + width / 2;

  return (
    <g>
      <line x1={cx} x2={cx} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect className="candle-body" x={x} y={bodyTop} width={width} height={bodyHeight} fill={color} />
    </g>
  );
};

export const CandlestickChart = ({ data }) => (
  <div data-testid="candlestick-chart" style={{ height: 260 }}>
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data}>
        <XAxis dataKey="date" tick={{ fill: 'var(--color-text-secondary)', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis domain={['dataMin', 'dataMax']} tick={{ fill: 'var(--color-text-secondary)', fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
        <Tooltip />
        <Bar dataKey={(d) => [d.low, d.high]} shape={Candle} />
        {EMA_LINES.map(([key, color]) => (
          <Line key={key} type="monotone" dataKey={key} dot={false} stroke={color} strokeWidth={1.5} connectNulls />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  </div>
);

export const VolumeChart = ({ data }) => (
  <div data-testid="volume-chart" style={{ height: 100, marginTop: 8 }}>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <XAxis dataKey="date" tick={{ fill: 'var(--color-text-secondary)', fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
        <Tooltip />
        <Bar dataKey="volume" fill={colors.accent} />
      </BarChart>
    </ResponsiveContainer>
  </div>
);
