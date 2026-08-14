import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import Portfolio from '../Portfolio';
import type { PortfolioHealth } from '../../api/portfolioHealth';

const HOLDING = {
  id: 'h1', symbol: 'GP', quantity: 10, buy_price: 250, current_price: 300,
  pnl: 500, pnl_percent: 20,
};

const HEALTH: PortfolioHealth = {
  holdings_valued: 1, total_value: 3000, is_default_profile: false, unweighted: false,
  findings: [{ kind: 'concentration', severity: 'warn', headline: 'Heavy in Telecom',
              reason: 'Telecom makes up most of your value.' }],
  disclaimer: 'Not financial advice.',
};

type GetFn = (url: string) => Promise<{ data: unknown }>;

function makeClient(overrides: { get?: GetFn } = {}): AxiosInstance {
  const get = vi.fn((url: string) => {
    if (url === '/portfolio') return Promise.resolve({ data: [HOLDING] });
    if (url === '/portfolio/summary') {
      return Promise.resolve({ data: { total_invested: 2500, current_value: 3000, total_pnl: 500, avg_pnl_pct: 20 } });
    }
    if (url === '/portfolio/health') return Promise.resolve({ data: HEALTH });
    return Promise.resolve({ data: {} });
  });
  return { get: overrides.get ?? get } as unknown as AxiosInstance;
}

describe('Portfolio (#97: wires up #91 health findings)', () => {
  it('renders holdings and summary', async () => {
    render(<Portfolio client={makeClient()} />);
    expect(await screen.findByText('GP')).toBeInTheDocument();
    expect(screen.getByText('2500.00')).toBeInTheDocument();
  });

  it('renders the portfolio health findings once fetched', async () => {
    render(<Portfolio client={makeClient()} />);
    expect(await screen.findByText('Heavy in Telecom')).toBeInTheDocument();
    expect(screen.getByText('Telecom makes up most of your value.')).toBeInTheDocument();
    expect(screen.getByText('Warn')).toBeInTheDocument();
    expect(screen.getByText('Not financial advice.')).toBeInTheDocument();
  });

  it('still renders the page when the health fetch fails', async () => {
    const get = vi.fn((url: string) => {
      if (url === '/portfolio') return Promise.resolve({ data: [HOLDING] });
      if (url === '/portfolio/summary') return Promise.resolve({ data: {} });
      if (url === '/portfolio/health') return Promise.reject(new Error('boom'));
      return Promise.resolve({ data: {} });
    });
    render(<Portfolio client={makeClient({ get })} />);
    expect(await screen.findByText('GP')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('Portfolio Health')).not.toBeInTheDocument());
  });
});
