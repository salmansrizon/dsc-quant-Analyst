import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../context/ThemeContext';
import CandlestickChart from '../CandlestickChart';

// jsdom has no canvas, so lightweight-charts can't actually paint — mock it
// and assert the integration contract (series data + theme colors) instead.
const setData = vi.fn();
const seriesApplyOptions = vi.fn();
const fitContent = vi.fn();
const chartApplyOptions = vi.fn();
const remove = vi.fn();
const addSeries = vi.fn(() => ({ setData, applyOptions: seriesApplyOptions }));

vi.mock('lightweight-charts', () => ({
  CandlestickSeries: 'candlestick-series-definition',
  ColorType: { Solid: 'solid' },
  createChart: vi.fn(() => ({
    addSeries,
    applyOptions: chartApplyOptions,
    remove,
    timeScale: () => ({ fitContent }),
  })),
}));

describe('CandlestickChart', () => {
  beforeEach(() => {
    setData.mockClear();
    seriesApplyOptions.mockClear();
    fitContent.mockClear();
    chartApplyOptions.mockClear();
    remove.mockClear();
    addSeries.mockClear();
  });

  it('renders the chart container and feeds it normalized OHLC data', () => {
    render(
      <ThemeProvider>
        <CandlestickChart
          data={[
            { Date: '2026-01-01', Open: 10, High: 12, Low: 9, Close: 11 },
            { Date: '2026-01-02', Open: 11, High: 13, Low: 10, Close: 10 },
          ] as never}
        />
      </ThemeProvider>,
    );

    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
    expect(addSeries).toHaveBeenCalledTimes(1);
    expect(setData).toHaveBeenCalledWith([
      { time: '2026-01-01', open: 10, high: 12, low: 9, close: 11 },
      { time: '2026-01-02', open: 11, high: 13, low: 10, close: 10 },
    ]);
    expect(fitContent).toHaveBeenCalled();
  });

  it('normalizes lowercase Candle rows the same way', () => {
    render(
      <ThemeProvider>
        <CandlestickChart data={[{ date: '2026-02-01', open: 5, high: 6, low: 4, close: 5.5 }]} />
      </ThemeProvider>,
    );
    expect(setData).toHaveBeenCalledWith([
      { time: '2026-02-01', open: 5, high: 6, low: 4, close: 5.5 },
    ]);
  });
});
