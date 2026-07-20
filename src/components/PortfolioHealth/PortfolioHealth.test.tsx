import { render, screen } from '@testing-library/react';
import PortfolioHealth, { type Health } from './PortfolioHealth';

const HEALTH: Health = {
  holdings_valued: 2, total_value: 3000, is_default_profile: false,
  disclaimer: 'Not financial advice.',
  findings: [
    { kind: 'concentration', severity: 'warn', headline: '80% in Bank',
      reason: 'Bank is 80% of your portfolio value — heavily concentrated.' },
    { kind: 'count', severity: 'caution', headline: '2 holdings',
      reason: '2 holdings — moderately diversified.' },
  ],
};

describe('PortfolioHealth (#91)', () => {
  it('renders each finding with a severity marker', () => {
    render(<PortfolioHealth health={HEALTH} />);
    expect(screen.getByText('80% in Bank')).toBeInTheDocument();
    expect(screen.getByText(/heavily concentrated/)).toBeInTheDocument();
    expect(screen.getByLabelText('warn')).toBeInTheDocument();
    expect(screen.getByText('Not financial advice.')).toBeInTheDocument();
  });

  it('renders nothing when there are no findings', () => {
    const { container } = render(
      <PortfolioHealth health={{ ...HEALTH, findings: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
