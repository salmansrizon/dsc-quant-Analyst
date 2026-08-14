import type { AxiosInstance } from 'axios';

export interface SectorComparisonMetric {
  metric: 'pe' | 'pb' | 'yield' | 'growth';
  label: string;
  subject_value: number | null;
  sector_median: number | null;
  peer_count: number;
  comparable: boolean;
}

export interface SectorComparison {
  symbol: string;
  sector: string | null;
  metrics: SectorComparisonMetric[];
}

// #92: fetched lazily — only when the (collapsed-by-default) Sector zone is
// first expanded, not on every Stock Detail page load.
export async function fetchSectorComparison(
  client: AxiosInstance,
  symbol: string,
): Promise<SectorComparison> {
  const { data } = await client.get<SectorComparison>(`/sector-comparison/${symbol}`);
  return data;
}
