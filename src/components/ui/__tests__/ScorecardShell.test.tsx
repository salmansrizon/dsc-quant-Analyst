import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ScorecardShell } from '../ScorecardShell';

describe('ScorecardShell', () => {
  it('renders every axis with its label and an explainer trigger for its reason', () => {
    render(
      <ScorecardShell
        axes={[
          { key: 'value', label: 'Value', reason: 'Trades below sector P/E.', badgeLabel: 'Strong', badgeVariant: 'positive' },
          { key: 'income', label: 'Income', reason: 'Below your stated dividend preference.', badgeLabel: 'Weak', badgeVariant: 'negative' },
        ]}
      />,
    );

    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('Income')).toBeInTheDocument();
    expect(screen.getByText('Strong')).toBeInTheDocument();
    expect(screen.getByText('Weak')).toBeInTheDocument();
    // one explainer trigger per axis — the reason string itself, per the map's
    // non-negotiable explainability rule.
    expect(screen.getAllByRole('button', { name: /what does this mean/i })).toHaveLength(2);
  });
});
