import { render, screen } from '@testing-library/react';
import CandlestickChart from '../CandlestickChart';

describe('CandlestickChart', () => {
  it('renders the chart container for capitalized price-history rows', () => {
    render(
      <CandlestickChart
        data={[
          { Date: '2026-01-01', Open: 10, High: 12, Low: 9, Close: 11 },
          { Date: '2026-01-02', Open: 11, High: 13, Low: 10, Close: 10 },
        ] as never}
      />,
    );
    expect(screen.getByTestId('candlestick-chart')).toBeInTheDocument();
  });
});
