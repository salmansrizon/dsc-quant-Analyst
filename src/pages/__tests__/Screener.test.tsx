import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import Screener from '../Screener';

function makeClient(results: unknown[] = []): AxiosInstance {
  return {
    post: vi.fn().mockResolvedValue({ data: { count: results.length, results } }),
  } as unknown as AxiosInstance;
}

function renderScreener(client: AxiosInstance) {
  return render(
    <MemoryRouter>
      <Screener client={client} />
    </MemoryRouter>,
  );
}

describe('Screener', () => {
  it('runs a preset and renders the result rows', async () => {
    const client = makeClient([
      { symbol: 'ACMELAB', sector: 'Pharma', price: 85.3, pe: 6.5, pb: 0.67, dividend_yield: 4.1 },
    ]);
    renderScreener(client);
    await userEvent.click(screen.getByRole('button', { name: 'Value' }));

    expect(await screen.findByText('ACMELAB')).toBeInTheDocument();
    expect(client.post).toHaveBeenCalledWith(
      '/market/screener',
      expect.objectContaining({ preset: 'value' }),
    );
  });

  it('surfaces a whitelist rejection from the API', async () => {
    const client = {
      post: vi.fn().mockRejectedValue({ response: { data: { detail: "Unknown field: 'foo'" } } }),
    } as unknown as AxiosInstance;
    renderScreener(client);
    await userEvent.click(screen.getByRole('button', { name: 'Growth' }));

    expect(await screen.findByText("Unknown field: 'foo'")).toBeInTheDocument();
  });

  it('enables bulk-add only once a row is selected', async () => {
    const client = makeClient([
      { symbol: 'GP', sector: 'Telecom', price: 257, pe: 13, pb: 6.2, dividend_yield: 8.3 },
    ]);
    renderScreener(client);
    await userEvent.click(screen.getByRole('button', { name: 'Value' }));
    await screen.findByText('GP');

    const addBtn = screen.getByRole('button', { name: /Add.*watchlist/ });
    expect(addBtn).toBeDisabled();
    await userEvent.click(screen.getByLabelText('select GP'));
    expect(addBtn).toBeEnabled();
  });
});
