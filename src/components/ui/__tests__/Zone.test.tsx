import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Zone } from '../Zone';

describe('Zone', () => {
  it('renders the zone label and children for a given zone type', () => {
    render(
      <Zone type="fit">
        <p>Axis content</p>
      </Zone>,
    );
    expect(screen.getByText('Fit for you')).toBeInTheDocument();
    expect(screen.getByText('Axis content')).toBeInTheDocument();
    expect(screen.getByTestId('zone-fit')).toBeInTheDocument();
  });

  it('renders a different label for a different zone type', () => {
    render(
      <Zone type="fundamentals">
        <p>Ratios</p>
      </Zone>,
    );
    expect(screen.getByText('Fundamentals')).toBeInTheDocument();
  });
});
