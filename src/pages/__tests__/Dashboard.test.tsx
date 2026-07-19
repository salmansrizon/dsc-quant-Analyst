import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import Dashboard from '../Dashboard';

// The dashboard fans out to several market endpoints; route each by URL.
function makeClient(): AxiosInstance {
  const get = vi.fn((url: string) => {
    if (url.startsWith('/market/strength')) {
      return Promise.resolve({ data: { Gainers: 180, Losers: 95, Unchanged: 25 } });
    }
    if (url.includes('metric=value')) {
      return Promise.resolve({ data: [{ Symbol: 'GP', LTP: 300, ChangePct: 1.2, Value: 9 }] });
    }
    if (url.includes('metric=gainer')) {
      return Promise.resolve({ data: [{ Symbol: 'ACI', LTP: 250, ChangePct: 8.4 }] });
    }
    // MarketSummary hits /market/summary — give it something benign.
    return Promise.resolve({ data: {} });
  });
  return { get } as unknown as AxiosInstance;
}

describe('Dashboard PRD-12 widgets', () => {
  it('renders the strength bar and leaderboard rows from the new endpoints', async () => {
    render(
      <MemoryRouter>
        <Dashboard client={makeClient()} />
      </MemoryRouter>,
    );
    expect(await screen.findByText('180 up')).toBeInTheDocument();
    expect(screen.getByText('95 down')).toBeInTheDocument();
    expect(await screen.findByText('GP')).toBeInTheDocument();
    expect(screen.getByText('ACI')).toBeInTheDocument();
  });
});
