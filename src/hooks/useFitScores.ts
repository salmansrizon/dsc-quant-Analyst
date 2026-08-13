import { useCallback, useEffect, useRef, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { fetchFitBatch, type FitScore } from '../api/fit';

export type FitScoreLookup = (symbol: string) => FitScore | undefined;

// #89: one shared fetch-and-cache hook for the fit scorecard, used by every
// page that lists stocks (Screener, Watchlist, Portfolio, Stock Detail) so
// each just passes its visible symbols instead of re-deriving this fetch.
//
// #90-architecture-review (candidate D): returns a callable lookup, not a
// raw dict — the symbol-casing convention (backend keys are uppercase) was
// duplicated at every call site as `dict[symbol.toUpperCase()]`, one missed
// `.toUpperCase()` away from a silent `undefined`. That normalization is now
// this hook's problem, not its callers'. The callable's identity stays
// stable across renders — a ref mirrors `scores` on every render so a
// useCallback with empty deps can read fresh data without depending on it.
// Motivated by the same class of bug ToastContext's api-object fix addressed
// (an unstable value handed to callers), but a different technique: that fix
// memoized the value itself; this one reads through a ref instead.
export function useFitScores(client: AxiosInstance, symbols: string[]): FitScoreLookup {
  const [scores, setScores] = useState<Record<string, FitScore>>({});
  const scoresRef = useRef(scores);
  scoresRef.current = scores;
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

  return useCallback((symbol: string) => scoresRef.current[symbol.toUpperCase()], []);
}
