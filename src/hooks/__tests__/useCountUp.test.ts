import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useCountUp } from '../useCountUp';

describe('useCountUp', () => {
  it('shows the initial value immediately, with no animate-from-zero on mount', () => {
    const { result } = renderHook(() => useCountUp(42));
    expect(result.current).toBe(42);
  });

  it('animates toward a new value and settles there', async () => {
    const { result, rerender } = renderHook(({ value }) => useCountUp(value, 50), {
      initialProps: { value: 100 },
    });
    expect(result.current).toBe(100);

    rerender({ value: 150 });

    await waitFor(() => expect(result.current).toBe(150));
  });
});
