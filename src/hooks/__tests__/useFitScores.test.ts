import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import { useFitScores } from '../useFitScores';
import type { FitScore } from '../../api/fit';

function fitFor(symbol: string): FitScore {
  return {
    symbol,
    composite: 50,
    scorable: true,
    weight_caption: '',
    axes: [{ axis: 'Value', score: 50, reason: 'r', weight: 1 }],
    is_default_profile: false,
    disclaimer: 'd',
  };
}

function makeClient(handler: (symbols: string[]) => Record<string, FitScore>) {
  return {
    post: vi.fn((_url: string, body: { symbols: string[] }) =>
      Promise.resolve({ data: handler(body.symbols) }),
    ),
  } as unknown as AxiosInstance;
}

describe('useFitScores (#89, deepened per the architecture-review D candidate)', () => {
  it('returns a callable lookup, not a raw dict', async () => {
    const client = makeClient((symbols) =>
      Object.fromEntries(symbols.map((s) => [s.toUpperCase(), fitFor(s.toUpperCase())])),
    );
    const { result } = renderHook(() => useFitScores(client, ['GP', 'ROBI']));

    expect(typeof result.current).toBe('function');
    await waitFor(() => expect(result.current('GP')).toBeDefined());
    expect(result.current('ROBI')).toBeDefined();
  });

  it('normalizes case internally — callers never touch .toUpperCase()', async () => {
    const client = makeClient((symbols) =>
      Object.fromEntries(symbols.map((s) => [s.toUpperCase(), fitFor(s.toUpperCase())])),
    );
    const { result } = renderHook(() => useFitScores(client, ['gp']));

    await waitFor(() => expect(result.current('gp')).toBeDefined());
    expect(result.current('GP')).toEqual(result.current('gp'));
    expect(result.current('Gp')).toEqual(result.current('gp'));
  });

  it('returns undefined for a symbol that was never requested', async () => {
    const client = makeClient((symbols) =>
      Object.fromEntries(symbols.map((s) => [s.toUpperCase(), fitFor(s.toUpperCase())])),
    );
    const { result } = renderHook(() => useFitScores(client, ['GP']));
    await waitFor(() => expect(result.current('GP')).toBeDefined());
    expect(result.current('UNKNOWN')).toBeUndefined();
  });

  it('does nothing for an empty symbol list', () => {
    const client = makeClient(() => ({}));
    const { result } = renderHook(() => useFitScores(client, []));
    expect(result.current('GP')).toBeUndefined();
    expect(client.post).not.toHaveBeenCalled();
  });

  it('refetches when the symbol set changes', async () => {
    const client = makeClient((symbols) =>
      Object.fromEntries(symbols.map((s) => [s.toUpperCase(), fitFor(s.toUpperCase())])),
    );
    const { result, rerender } = renderHook(({ symbols }) => useFitScores(client, symbols), {
      initialProps: { symbols: ['GP'] },
    });
    await waitFor(() => expect(result.current('GP')).toBeDefined());

    rerender({ symbols: ['GP', 'ROBI'] });
    await waitFor(() => expect(result.current('ROBI')).toBeDefined());
    expect(client.post).toHaveBeenCalledTimes(2);
  });

  it('keeps a stable function identity across re-renders (same lesson as the ToastContext fix)', async () => {
    const client = makeClient((symbols) =>
      Object.fromEntries(symbols.map((s) => [s.toUpperCase(), fitFor(s.toUpperCase())])),
    );
    const { result, rerender } = renderHook(({ symbols }) => useFitScores(client, symbols), {
      initialProps: { symbols: ['GP'] },
    });
    const first = result.current;
    await waitFor(() => expect(result.current('GP')).toBeDefined());

    rerender({ symbols: ['GP'] });
    expect(result.current).toBe(first);
  });
});
