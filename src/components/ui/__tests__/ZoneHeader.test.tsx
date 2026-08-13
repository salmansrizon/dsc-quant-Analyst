import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ZoneHeader } from '../ZoneHeader';

describe('ZoneHeader', () => {
  it('renders the label for the given zone type', () => {
    render(<ZoneHeader type="fundamentals" />);
    expect(screen.getByText('Fundamentals')).toBeInTheDocument();
  });

  it('renders a different label for a different zone type', () => {
    render(<ZoneHeader type="fit" />);
    expect(screen.getByText('Fit for you')).toBeInTheDocument();
  });
});
