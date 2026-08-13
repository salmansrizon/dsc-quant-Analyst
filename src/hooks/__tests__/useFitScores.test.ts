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

describe('useFitScores (#89)', () => {
  it('fetches the batch for the given symbols on mount', async () => {
    const client = makeClient((symbols) =>
      Object.fromEntries(symbols.map((s) => [s.toUpperCase(), fitFor(s.toUpperCase())])),
    );
    const { result } = renderHook(() => useFitScores(client, ['GP', 'ROBI']));

    await waitFor(() => expect(Object.keys(result.current)).toEqual(['GP', 'ROBI']));
    expect(client.post).toHaveBeenCalledTimes(1);
  });

  it('does nothing for an empty symbol list', () => {
    const client = makeClient(() => ({}));
    const { result } = renderHook(() => useFitScores(client, []));
    expect(result.current).toEqual({});
    expect(client.post).not.toHaveBeenCalled();
  });

  it('refetches when the symbol set changes', async () => {
    const client = makeClient((symbols) =>
      Object.fromEntries(symbols.map((s) => [s.toUpperCase(), fitFor(s.toUpperCase())])),
    );
    const { result, rerender } = renderHook(({ symbols }) => useFitScores(client, symbols), {
      initialProps: { symbols: ['GP'] },
    });
    await waitFor(() => expect(Object.keys(result.current)).toEqual(['GP']));

    rerender({ symbols: ['GP', 'ROBI'] });
    await waitFor(() => expect(Object.keys(result.current).sort()).toEqual(['GP', 'ROBI']));
    expect(client.post).toHaveBeenCalledTimes(2);
  });
});
