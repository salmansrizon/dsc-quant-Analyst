import { render, screen, waitFor } from '@testing-library/react';
import { useEffect, useRef } from 'react';
import { describe, expect, it } from 'vitest';
import { ToastProvider, useToast } from '../ToastContext';

describe('ToastContext', () => {
  it('keeps the toast api reference stable across renders', () => {
    const seen: unknown[] = [];

    function Probe({ tick }: { tick: number }) {
      const toast = useToast();
      seen.push(toast);
      return <span>{tick}</span>;
    }

    const { rerender } = render(
      <ToastProvider>
        <Probe tick={0} />
      </ToastProvider>,
    );
    rerender(
      <ToastProvider>
        <Probe tick={1} />
      </ToastProvider>,
    );

    expect(seen.length).toBe(2);
    expect(new Set(seen).size).toBe(1);
  });

  it('does not loop an effect that depends on `toast` and calls toast.error on failure', async () => {
    let effectRuns = 0;

    function FailingFetcher() {
      const toast = useToast();
      const ranOnce = useRef(false);
      useEffect(() => {
        effectRuns += 1;
        if (!ranOnce.current) {
          ranOnce.current = true;
          toast.error('boom');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, [toast]);
      return null;
    }

    render(
      <ToastProvider>
        <FailingFetcher />
      </ToastProvider>,
    );

    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument());
    // A stable `toast` means this effect runs once (mount), not once per
    // toast — before the #90 fix this ran unboundedly.
    expect(effectRuns).toBe(1);
  });
});
