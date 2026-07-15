import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import AlertsPage from '../AlertsPage';

function makeClient(alerts: unknown[] = []): AxiosInstance {
  return {
    get: vi.fn().mockResolvedValue({ data: alerts }),
    post: vi.fn().mockResolvedValue({ data: { id: 'x', symbol: 'REL', target_price: 50, direction: 'above', is_triggered: false } }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  } as unknown as AxiosInstance;
}

describe('AlertsPage', () => {
  it('shows the empty state when there are no alerts', async () => {
    render(<AlertsPage client={makeClient([])} />);
    expect(await screen.findByText('No alerts set.')).toBeInTheDocument();
  });

  it('validates before posting a new alert', async () => {
    const client = makeClient([]);
    render(<AlertsPage client={client} />);
    await screen.findByText('No alerts set.');
    await userEvent.click(screen.getByRole('button', { name: 'Add Alert' }));
    expect(screen.getByText('Provide a valid symbol and price')).toBeInTheDocument();
    expect(client.post).not.toHaveBeenCalled();
  });

  it('renders existing alerts in a table', async () => {
    const client = makeClient([
      { id: '1', symbol: 'GP', target_price: 300, direction: 'above', is_triggered: false },
    ]);
    render(<AlertsPage client={client} />);
    expect(await screen.findByText('GP')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });
});
