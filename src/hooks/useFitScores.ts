import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { fetchFitBatch, type FitScore } from '../api/fit';

// #89: one shared fetch-and-cache hook for the fit scorecard, used by every
// page that lists stocks (Screener, Watchlist, Portfolio, Stock Detail) so
// each just passes its visible symbols instead of re-deriving this fetch.
export function useFitScores(client: AxiosInstance, symbols: string[]): Record<string, FitScore> {
  const [scores, setScores] = useState<Record<string, FitScore>>({});
  const key = symbols.join(',');

  useEffect(() => {
    if (symbols.length === 0) return;
    let cancelled = false;
    fetchFitBatch(client, symbols)
      .then((result) => {
        if (!cancelled) setScores((prev) => ({ ...prev, ...result }));
      })
      .catch(() => {
        /* best-effort — rows just render without a fit scorecard */
      });
    return () => {
      cancelled = true;
    };
    // symbols is intentionally represented by `key` — a stable join, not the
    // array identity, so an equal-but-new-array doesn't refetch.
  }, [client, key]);

  return scores;
}
