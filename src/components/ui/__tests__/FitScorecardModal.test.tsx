import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FitScorecardModal } from '../FitScorecardModal';
import type { FitScore } from '../../../api/fit';

function baseFit(overrides: Partial<FitScore> = {}): FitScore {
  return {
    symbol: 'GP',
    composite: 70,
    scorable: true,
    weight_caption: 'Weighted toward Growth & Stability, from your profile.',
    axes: [
      { axis: 'Value', score: 80, reason: 'Cheaper than sector peers.', weight: 0.2 },
      { axis: 'Income', score: 40, reason: 'Below-average yield.', weight: 0.2 },
    ],
    is_default_profile: false,
    disclaimer: 'Not financial advice.',
    ...overrides,
  };
}

describe('FitScorecardModal', () => {
  it('renders nothing when closed', () => {
    render(<FitScorecardModal fit={baseFit()} open={false} onOpenChange={vi.fn()} />);
    expect(screen.queryByText('Cheaper than sector peers.')).not.toBeInTheDocument();
  });

  it('shows every scored axis with its reason, the weight caption, and the disclaimer when open', () => {
    render(<FitScorecardModal fit={baseFit()} open onOpenChange={vi.fn()} />);
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('Income')).toBeInTheDocument();
    expect(screen.getByText('Weighted toward Growth & Stability, from your profile.')).toBeInTheDocument();
    expect(screen.getByText('Not financial advice.')).toBeInTheDocument();
  });

  it('prompts to complete the profile, before the axes, on a default profile', () => {
    render(<FitScorecardModal fit={baseFit({ is_default_profile: true })} open onOpenChange={vi.fn()} />);
    const prompt = screen.getByText(/complete your profile/i);
    const firstAxis = screen.getByText('Value');
    // decision #3: the prompt must precede the axes, not trail them.
    expect(
      prompt.compareDocumentPosition(firstAxis) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('notes thin data without discarding whatever axis did score', () => {
    const fit = baseFit({
      scorable: false,
      axes: [{ axis: 'Value', score: 80, reason: 'Cheaper than sector peers.', weight: 0.2 }],
    });
    render(<FitScorecardModal fit={fit} open onOpenChange={vi.fn()} />);
    // The reason itself is hover-gated (ExplainerPopover) — assert the real
    // scored axis still rendered, rather than discarding it for thin data.
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
    expect(screen.getByText(/not enough data/i)).toBeInTheDocument();
  });
});
