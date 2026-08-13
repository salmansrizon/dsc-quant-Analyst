import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ScoreBar } from '../ScoreBar';

describe('ScoreBar', () => {
  it('renders a fill width proportional to the score', () => {
    render(<ScoreBar score={80} />);
    const fill = screen.getByTestId('score-bar-fill');
    expect(fill).toHaveStyle({ width: '80%' });
  });

  it('clamps out-of-range scores into 0..100', () => {
    render(<ScoreBar score={150} />);
    expect(screen.getByTestId('score-bar-fill')).toHaveStyle({ width: '100%' });
  });

  it('exposes the score to assistive tech via a progressbar role', () => {
    render(<ScoreBar score={42} />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '42');
  });
});
