import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PriceChange from '../PriceChange';

describe('PriceChange', () => {
  it('renders nothing when the change is unknown', () => {
    const { container } = render(<PriceChange pct={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows a positive change with a + prefix', () => {
    render(<PriceChange pct={2.5} />);
    expect(screen.getByText('+2.50%')).toBeInTheDocument();
  });

  it('shows a negative change without a + prefix', () => {
    render(<PriceChange pct={-1.234} />);
    expect(screen.getByText('-1.23%')).toBeInTheDocument();
  });
});
