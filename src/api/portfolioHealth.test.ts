import { describe, expect, it, vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import { fetchPortfolioHealth, type PortfolioHealth } from './portfolioHealth';

describe('fetchPortfolioHealth (#97)', () => {
  it('gets /portfolio/health with no params', async () => {
    const health: PortfolioHealth = {
      holdings_valued: 3, total_value: 15000, is_default_profile: false, unweighted: false,
      findings: [{ kind: 'concentration', severity: 'warn', headline: 'Heavy in Bank',
                  reason: 'Bank makes up most of your value.' }],
      disclaimer: 'Not financial advice.',
    };
    const client = { get: vi.fn().mockResolvedValue({ data: health }) } as unknown as AxiosInstance;

    const result = await fetchPortfolioHealth(client);

    expect(client.get).toHaveBeenCalledWith('/portfolio/health');
    expect(result).toEqual(health);
  });
});
