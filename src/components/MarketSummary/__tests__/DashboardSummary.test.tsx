import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import MarketSummary from '../DashboardSummary';

const mockData = {
  summary: { ltp: '123.45', change: '+1.23%' },
  sectors: [
    { name: 'Tech', count: 150, change: 2.5 },
    { name: 'Finance', count: 85, change: -1.2 },
  ],
};

function mockClient(data: unknown): AxiosInstance {
  return { get: vi.fn().mockResolvedValue({ data }) } as unknown as AxiosInstance;
}

describe('DashboardSummary', () => {
  it('renders LTP and sector names once loaded', async () => {
    render(<MarketSummary client={mockClient(mockData)} />);
    expect(await screen.findByText('LTP: 123.45')).toBeInTheDocument();
    expect(screen.getByText('Tech')).toBeInTheDocument();
    expect(screen.getByText('Finance')).toBeInTheDocument();
  });

  it('renders defensively when the payload has no summary/sectors', async () => {
    render(<MarketSummary client={mockClient({ total_stocks: 5 })} />);
    expect(await screen.findByText('LTP: —')).toBeInTheDocument();
  });
});
