import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { FitScorecard } from '../FitScorecard';
import type { FitScore } from '../../../api/fit';

function baseFit(overrides: Partial<FitScore> = {}): FitScore {
  return {
    symbol: 'GP',
    composite: 70,
    scorable: true,
    weight_caption: 'Weighted toward Growth & Stability, from your profile.',
    axes: [
      { axis: 'Value', score: 80, reason: 'Cheaper than sector peers.', weight: 0.2 },
      { axis: 'Income', score: 20, reason: 'Below-average yield.', weight: 0.2 },
      { axis: 'Growth', score: null, reason: 'EPS history unavailable.', weight: 0 },
    ],
    is_default_profile: false,
    disclaimer: 'Not financial advice.',
    ...overrides,
  };
}

describe('FitScorecard', () => {
  it('renders nothing while the fit score has not loaded yet', () => {
    const { container } = render(<FitScorecard fit={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders one chip per scored axis, dropping null-score axes', () => {
    render(<FitScorecard fit={baseFit()} />);
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('Income')).toBeInTheDocument();
    expect(screen.queryByText('Growth')).not.toBeInTheDocument();
  });

  it('shows a thin-data chip when the score is not scorable', () => {
    render(<FitScorecard fit={baseFit({ scorable: false })} />);
    expect(screen.getByText(/thin data/i)).toBeInTheDocument();
  });

  it('shows per-axis reasons on hover', async () => {
    const user = userEvent.setup();
    render(<FitScorecard fit={baseFit()} />);

    expect(screen.queryByText('Cheaper than sector peers.')).not.toBeInTheDocument();
    await user.hover(screen.getByTestId('fit-scorecard-trigger'));
    await waitFor(() =>
      expect(screen.getByText('Cheaper than sector peers.')).toBeInTheDocument(),
    );
  });

  it('opens the full-view modal on click', async () => {
    const user = userEvent.setup();
    render(<FitScorecard fit={baseFit()} />);

    expect(screen.queryByText('Not financial advice.')).not.toBeInTheDocument();
    await user.click(screen.getByTestId('fit-scorecard-trigger'));
    await waitFor(() => expect(screen.getByText('Not financial advice.')).toBeInTheDocument());
  });
});
