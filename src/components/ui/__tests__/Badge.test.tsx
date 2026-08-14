import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Badge } from '../Badge';

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge variant="positive">Strong fit</Badge>);
    expect(screen.getByText('Strong fit')).toBeInTheDocument();
  });

  it('defaults to the neutral variant', () => {
    render(<Badge>Unrated</Badge>);
    expect(screen.getByText('Unrated')).toBeInTheDocument();
  });
});
