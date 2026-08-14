import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ExplainerPopover } from '../ExplainerPopover';

describe('ExplainerPopover', () => {
  it('shows the reason string on hover, not by default', async () => {
    const user = userEvent.setup();
    render(<ExplainerPopover>Matches your growth preference.</ExplainerPopover>);

    expect(screen.queryByText('Matches your growth preference.')).not.toBeInTheDocument();

    await user.hover(screen.getByRole('button', { name: /what does this mean/i }));

    await waitFor(
      () => expect(screen.getByText('Matches your growth preference.')).toBeInTheDocument(),
      { timeout: 2000 },
    );
  });
});
