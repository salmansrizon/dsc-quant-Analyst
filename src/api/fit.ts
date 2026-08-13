import type { AxiosInstance } from 'axios';

export interface FitAxis {
  axis: string;
  score: number | null;
  reason: string;
  weight: number;
}

export interface FitScore {
  symbol: string;
  composite: number | null;
  scorable: boolean;
  weight_caption: string;
  axes: FitAxis[];
  is_default_profile: boolean;
  disclaimer: string;
}

// #89: the batched seam a page with many visible rows calls through once
// instead of one GET /fit/{symbol} per row — mirrors the backend's score_many.
export async function fetchFitBatch(
  client: AxiosInstance,
  symbols: string[],
): Promise<Record<string, FitScore>> {
  if (symbols.length === 0) return {};
  const { data } = await client.post<Record<string, FitScore>>('/fit/batch', { symbols });
  return data;
}
