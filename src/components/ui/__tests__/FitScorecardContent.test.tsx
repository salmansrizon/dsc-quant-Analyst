import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FitScorecardContent } from '../FitScorecardContent';
import type { FitScore } from '../../../api/fit';

function baseFit(overrides: Partial<FitScore> = {}): FitScore {
  return {
    symbol: 'GP',
    composite: 70,
    scorable: true,
    weight_caption: 'Weighted toward Growth & Stability, from your profile.',
    axes: [
      { axis: 'Value', score: 80, reason: 'Cheaper than sector peers.', weight: 0.2 },
      { axis: 'Growth', score: null, reason: 'EPS history unavailable.', weight: 0 },
    ],
    is_default_profile: false,
    disclaimer: 'Not financial advice.',
    ...overrides,
  };
}

describe('FitScorecardContent', () => {
  it('renders a ScoreBar meter alongside each scored axis, dropping null axes', () => {
    render(<FitScorecardContent fit={baseFit()} />);
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('80')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '80');
    expect(screen.queryByText('Growth')).not.toBeInTheDocument();
  });

  it('shows the weight caption and disclaimer', () => {
    render(<FitScorecardContent fit={baseFit()} />);
    expect(screen.getByText('Weighted toward Growth & Stability, from your profile.')).toBeInTheDocument();
    expect(screen.getByText('Not financial advice.')).toBeInTheDocument();
  });
});
