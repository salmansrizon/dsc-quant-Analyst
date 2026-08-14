import { describe, expect, it, vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import { fetchSectorComparison, type SectorComparison } from './sectorComparison';

function makeClient(data: SectorComparison) {
  return { get: vi.fn().mockResolvedValue({ data }) } as unknown as AxiosInstance;
}

describe('fetchSectorComparison (#92)', () => {
  it('gets the sector comparison for a symbol', async () => {
    const payload: SectorComparison = {
      symbol: 'GP',
      sector: 'Telecom',
      metrics: [
        { metric: 'pe', label: 'P/E', subject_value: 10, sector_median: 16, peer_count: 5, comparable: true },
      ],
    };
    const client = makeClient(payload);

    const result = await fetchSectorComparison(client, 'gp');

    expect(client.get).toHaveBeenCalledWith('/sector-comparison/gp');
    expect(result).toEqual(payload);
  });
});
