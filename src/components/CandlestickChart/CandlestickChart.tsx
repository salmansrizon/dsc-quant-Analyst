import {
  CandlestickSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';
import type { Candle } from '../PriceChart/PriceChart';

interface OHLC {
  time: string;
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
  return { time: date, open, high, low, close };
}

function cssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

// #87: reads the design tokens live (not hard-coded) so the chart follows the
// light/dark toggle — lightweight-charts paints to canvas, so colors must be
// resolved to literal strings rather than left as var(--x) references.
function chartLayoutOptions() {
  const borderColor = cssVar('--border-color', '#2b303c');
  return {
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: cssVar('--text-secondary', '#9aa1ad'),
    },
    grid: {
      vertLines: { color: borderColor },
      horzLines: { color: borderColor },
    },
    timeScale: { borderColor },
    rightPriceScale: { borderColor },
  };
}

function candleSeriesOptions() {
  const up = cssVar('--accent-green', '#34d399');
  const down = cssVar('--accent-red', '#f87171');
  return {
    upColor: up,
    downColor: down,
    borderVisible: false,
    wickUpColor: up,
    wickDownColor: down,
  };
}

export default function CandlestickChart({ data }: { data: Candle[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, { autoSize: true, ...chartLayoutOptions() });
    const series = chart.addSeries(CandlestickSeries, candleSeriesOptions());
    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Re-apply resolved colors whenever the light/dark toggle flips.
  useEffect(() => {
    chartRef.current?.applyOptions(chartLayoutOptions());
    seriesRef.current?.applyOptions(candleSeriesOptions());
  }, [theme]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const points = data
      .map(toOHLC)
      .filter((d) => d.time)
      .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    series.setData(points as never);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return <div ref={containerRef} data-testid="candlestick-chart" style={{ height: 300 }} />;
}
