import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { useState } from 'react';
import type { AxiosInstance } from 'axios';
import SymbolSearch, { type MarketRow } from '../SymbolSearch';

function makeClient(rows: MarketRow[]): AxiosInstance {
  return { get: vi.fn().mockResolvedValue({ data: rows }) } as unknown as AxiosInstance;
}

// Controlled wrapper: SymbolSearch owns nothing, so a test host holds the text.
function Host({ client, onSelect }: { client: AxiosInstance; onSelect?: (r: MarketRow) => void }) {
  const [value, setValue] = useState('');
  return <SymbolSearch client={client} value={value} onChange={setValue} onSelect={onSelect} />;
}

describe('SymbolSearch', () => {
  it('queries market/stocks (debounced) and shows suggestions', async () => {
    const client = makeClient([{ Symbol: 'GP', Sector: 'Telecom', LTP: 300, ChangePct: 1.2 }]);
    render(<Host client={client} />);
    await userEvent.type(screen.getByPlaceholderText('Search symbol…'), 'GP');
    expect(await screen.findByText('GP')).toBeInTheDocument();
    expect(client.get).toHaveBeenCalledWith('/market/stocks?search=GP&limit=8');
  });

  it('fires onSelect with the full row when a suggestion is clicked', async () => {
    const row: MarketRow = { Symbol: 'GP', Sector: 'Telecom', LTP: 300, ChangePct: 1.2 };
    const onSelect = vi.fn();
    render(<Host client={makeClient([row])} onSelect={onSelect} />);
    await userEvent.type(screen.getByPlaceholderText('Search symbol…'), 'GP');
    await screen.findByRole('option');
    // choose() lives on the suggestion button's onMouseDown, so click the button.
    await userEvent.click(screen.getByRole('button', { name: /GP/ }));
    expect(onSelect).toHaveBeenCalledWith(row);
  });

  it('does not query for empty input', async () => {
    const client = makeClient([]);
    render(<Host client={client} />);
    await waitFor(() => expect(client.get).not.toHaveBeenCalled());
  });
});
