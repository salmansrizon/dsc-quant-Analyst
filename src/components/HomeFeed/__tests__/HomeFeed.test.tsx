import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import { AuthContext, type User } from '../../../context/AuthContext';
import HomeFeed from '../HomeFeed';
import type { Feed } from '../../../api/feed';

const user: User = { id: 'u1', email: 'a@x.com', role: 'user' };

type GetFn = (url: string, config?: { params?: { limit?: number; offset?: number } }) => Promise<{ data: Feed }>;

function renderFeed(get: GetFn, authedUser: User | null = user) {
  const client = { get: vi.fn(get) } as unknown as AxiosInstance;
  const ctx = { user: authedUser, token: 't', login: async () => {}, logout: () => {} };
  render(
    <AuthContext.Provider value={ctx}>
      <MemoryRouter>
        <HomeFeed client={client} />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
  return client;
}

const PAGE1: Feed = {
  items: [
    { kind: 'nudge', headline: 'Explore Pharma', reason: 'you hold none in Pharma',
      symbols: ['PH1', 'PH2'], sources: [] },
    { kind: 'recommendation', headline: 'GP — strong match', reason: 'high yield, in your sector',
      symbol: 'GP', symbols: [], sources: ['fit'] },
  ],
  next_offset: 2,
  is_default_profile: false,
  disclaimer: 'Not financial advice.',
};

const PAGE2: Feed = {
  items: [{ kind: 'alert', headline: 'Alert active on SQUARE', reason: 'Your price alert on SQUARE is active.',
            symbol: 'SQUARE', symbols: [], sources: [] }],
  next_offset: null,
  is_default_profile: false,
  disclaimer: 'Not financial advice.',
};

describe('HomeFeed (#96)', () => {
  it('renders nothing for a logged-out visitor and never calls the feed endpoint', () => {
    const get = vi.fn();
    renderFeed(get, null);
    expect(screen.queryByTestId('home-feed')).not.toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it('fetches page 1 and renders headline/reason/kind label/symbol links', async () => {
    renderFeed(async () => ({ data: PAGE1 }));

    expect(await screen.findByText('Explore Pharma')).toBeInTheDocument();
    expect(screen.getByText('you hold none in Pharma')).toBeInTheDocument();
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('GP — strong match')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'For You' })).toBeInTheDocument();

    const gpLink = screen.getByRole('link', { name: 'GP' });
    expect(gpLink).toHaveAttribute('href', '/stock/GP');
    expect(screen.getByRole('link', { name: 'PH1' })).toHaveAttribute('href', '/stock/PH1');

    expect(screen.getByText('Not financial advice.')).toBeInTheDocument();
  });

  it('shows an empty state when the feed has no items', async () => {
    renderFeed(async () => ({ data: { items: [], next_offset: null, is_default_profile: false, disclaimer: 'd' } }));
    expect(await screen.findByText('Nothing new right now.')).toBeInTheDocument();
  });

  it('shows a complete-your-profile note when the feed reports the default profile', async () => {
    renderFeed(async () => ({
      data: {
        items: [{ kind: 'nudge', headline: 'Set your investor profile', reason: 'do it', symbols: [], sources: [] }],
        next_offset: null, is_default_profile: true, disclaimer: 'd',
      },
    }));
    expect(await screen.findByText('Complete your profile to personalize your feed.')).toBeInTheDocument();
  });

  it('loads the next page and appends items on "Load more"', async () => {
    const get: GetFn = vi.fn(async (_url, config) =>
      config?.params?.offset === 2 ? { data: PAGE2 } : { data: PAGE1 });
    renderFeed(get);

    await screen.findByText('Explore Pharma');
    const loadMore = screen.getByRole('button', { name: 'Load more' });
    await userEvent.click(loadMore);

    expect(await screen.findByText('Alert active on SQUARE')).toBeInTheDocument();
    // Page 1 items stay mounted — appended, not replaced.
    expect(screen.getByText('Explore Pharma')).toBeInTheDocument();
    // No more pages after page 2 (next_offset: null) — button disappears.
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument());

    expect(get).toHaveBeenCalledWith('/feed', { params: { limit: 20, offset: 0 } });
    expect(get).toHaveBeenCalledWith('/feed', { params: { limit: 20, offset: 2 } });
  });
});
