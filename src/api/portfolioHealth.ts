import type { AxiosInstance } from 'axios';

export type FindingSeverity = 'good' | 'caution' | 'warn';

export interface PortfolioFinding {
  kind: string;
  severity: FindingSeverity;
  headline: string;
  reason: string;
}

export interface PortfolioHealth {
  holdings_valued: number;
  total_value: number;
  is_default_profile: boolean;
  unweighted: boolean;
  findings: PortfolioFinding[];
  disclaimer: string;
}

// #97: wires up #91's previously-unrendered portfolio-health seam.
export async function fetchPortfolioHealth(client: AxiosInstance): Promise<PortfolioHealth> {
  const { data } = await client.get<PortfolioHealth>('/portfolio/health');
  return data;
}
