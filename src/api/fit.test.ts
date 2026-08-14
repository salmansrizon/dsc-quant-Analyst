import { describe, expect, it, vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import { fetchFitBatch, type FitScore } from './fit';

function makeClient(data: Record<string, FitScore>) {
  return { post: vi.fn().mockResolvedValue({ data }) } as unknown as AxiosInstance;
}

describe('fetchFitBatch (#89)', () => {
  it('posts the batched seam and returns the symbol-keyed response', async () => {
    const gp: FitScore = {
      symbol: 'GP',
      composite: 70,
      scorable: true,
      weight_caption: 'Weighted toward Growth & Stability, from your profile.',
      axes: [{ axis: 'Value', score: 80, reason: 'Cheaper than sector peers.', weight: 0.2 }],
      is_default_profile: false,
      disclaimer: 'Not financial advice.',
    };
    const client = makeClient({ GP: gp });

    const result = await fetchFitBatch(client, ['gp']);

    expect(client.post).toHaveBeenCalledWith('/fit/batch', { symbols: ['gp'] });
    expect(result).toEqual({ GP: gp });
  });

  it('skips the request entirely for an empty symbol list', async () => {
    const client = makeClient({});
    const result = await fetchFitBatch(client, []);
    expect(client.post).not.toHaveBeenCalled();
    expect(result).toEqual({});
  });
});
