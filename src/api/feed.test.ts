import { describe, expect, it, vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import { fetchFeed, type Feed } from './feed';

function makeClient(data: Feed) {
  return { get: vi.fn().mockResolvedValue({ data }) } as unknown as AxiosInstance;
}

describe('fetchFeed (#96)', () => {
  it('gets the paginated feed with limit/offset params', async () => {
    const feed: Feed = {
      items: [{ kind: 'nudge', headline: 'Explore Pharma', reason: 'you hold none',
                symbols: ['PH1'], sources: [] }],
      next_offset: 20,
      is_default_profile: false,
      disclaimer: 'Not financial advice.',
    };
    const client = makeClient(feed);

    const result = await fetchFeed(client, 20, 0);

    expect(client.get).toHaveBeenCalledWith('/feed', { params: { limit: 20, offset: 0 } });
    expect(result).toEqual(feed);
  });

  it('defaults to limit 20 offset 0', async () => {
    const feed: Feed = { items: [], next_offset: null, is_default_profile: false, disclaimer: 'd' };
    const client = makeClient(feed);

    await fetchFeed(client);

    expect(client.get).toHaveBeenCalledWith('/feed', { params: { limit: 20, offset: 0 } });
  });
});
