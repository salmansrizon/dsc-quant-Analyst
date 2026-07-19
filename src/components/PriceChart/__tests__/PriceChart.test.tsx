import { render, screen } from '@testing-library/react';
import PriceChart from '../PriceChart';

const data = [
  { date: '2024-01-01', close: 103 },
  { date: '2024-01-02', close: 107 },
  { date: '2024-01-03', close: 106 },
];

describe('PriceChart', () => {
  it('renders the symbol heading', () => {
    render(<PriceChart data={data} symbol="AAPL" />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
  });

  it('accepts the legacy `candles` prop alias', () => {
    render(<PriceChart candles={data} symbol="BEXIMCO" />);
    expect(screen.getByText('BEXIMCO')).toBeInTheDocument();
  });

  it('shows an empty state with no data', () => {
    render(<PriceChart data={[]} symbol="EMPTY" />);
    expect(screen.getByText('No price data')).toBeInTheDocument();
  });
});
