import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CollapsibleZone } from '../CollapsibleZone';

describe('CollapsibleZone', () => {
  it('renders its zone label and starts open when defaultOpen is true', () => {
    render(
      <CollapsibleZone type="fundamentals" defaultOpen>
        <p>Ratios table</p>
      </CollapsibleZone>,
    );
    expect(screen.getByText('Fundamentals')).toBeInTheDocument();
    expect(screen.getByText('Ratios table')).toBeInTheDocument();
  });

  it('starts closed when defaultOpen is false, and the whole header toggles it', async () => {
    const user = userEvent.setup();
    render(
      <CollapsibleZone type="fundamentals" defaultOpen={false}>
        <p>Ratios table</p>
      </CollapsibleZone>,
    );
    expect(screen.queryByText('Ratios table')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /fundamentals/i }));
    expect(screen.getByText('Ratios table')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /fundamentals/i }));
    expect(screen.queryByText('Ratios table')).not.toBeInTheDocument();
  });

  it('calls onOpenChange with the new open state on every toggle (#92: lazy-fetch trigger)', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(
      <CollapsibleZone type="sector" defaultOpen={false} onOpenChange={onOpenChange}>
        <p>Comparison</p>
      </CollapsibleZone>,
    );

    await user.click(screen.getByRole('button', { name: /sector comparison/i }));
    expect(onOpenChange).toHaveBeenCalledWith(true);

    await user.click(screen.getByRole('button', { name: /sector comparison/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
