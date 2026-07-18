import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import StockDetail from '../StockDetail';

const FUND = {
  symbol: 'GP',
  price: 257.5,
  market_cap_bdt_bn: 350.67,
  pe: 13.29,
  reported: {
    ROE: {
      value: 0.42,
      reported_as: 'Return on Equity',
      category: 'Profitability',
      year: 2025,
      equation: 'x / y',
      sign_inverted: false,
    },
  },
  derived: {
    price_to_book: 6.2,
    dividend_yield_pct: 8.35,
    dividend_year: 2025,
    cash_dividend_pct: 215,
    eps_growth_pct: 3.71,
    peg: 3.58,
  },
  eps_history: [{ year: 2025, eps: 21.9, nav: 41.49 }],
  caveats: ['Face value is assumed to be 10 BDT for every symbol.'],
};

function makeClient(): AxiosInstance {
  return {
    get: vi.fn((url: string) =>
      url.includes('/fundamentals/')
        ? Promise.resolve({ data: FUND })
        : Promise.resolve({ data: [{ Date: '2025-01-01', Close: 250 }] }),
    ),
  } as unknown as AxiosInstance;
}

function renderDetail(client: AxiosInstance) {
  return render(
    <MemoryRouter initialEntries={['/stock/GP']}>
      <Routes>
        <Route path="/stock/:symbol" element={<StockDetail client={client} />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('StockDetail', () => {
  it('renders the symbol header and a reported ratio', async () => {
    renderDetail(makeClient());
    expect(await screen.findByRole('heading', { name: 'GP', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Return on Equity')).toBeInTheDocument();
    expect(screen.getByText('PEG')).toBeInTheDocument();
  });

  it('shows the caveat text', async () => {
    renderDetail(makeClient());
    expect(
      await screen.findByText(/Face value is assumed to be 10 BDT/),
    ).toBeInTheDocument();
  });

  it('shows an error when the fundamentals fetch fails', async () => {
    const client = {
      get: vi.fn().mockRejectedValue(new Error('boom')),
    } as unknown as AxiosInstance;
    renderDetail(client);
    expect(await screen.findByText('Failed to load GP')).toBeInTheDocument();
  });
});
