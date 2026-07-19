import { render, screen } from '@testing-library/react';
import SectorGrid from '../SectorGrid';

const sectors = [
  { sector: 'Tech', count: 150, change: 2.5 },
  { sector: 'Finance', count: 85, change: -1.2 },
];

describe('SectorGrid', () => {
  it('renders each sector with count and signed change', () => {
    render(<SectorGrid sectors={sectors} />);
    expect(screen.getByText('Tech')).toBeInTheDocument();
    expect(screen.getByText('Finance')).toBeInTheDocument();
    expect(screen.getByText('150 stocks')).toBeInTheDocument();
    expect(screen.getByText('2.50%')).toBeInTheDocument();
    expect(screen.getByText('-1.20%')).toBeInTheDocument();
  });

  it('colors gains green and losses red', () => {
    render(<SectorGrid sectors={sectors} />);
    expect(screen.getByText('2.50%')).toHaveClass('text-green-600');
    expect(screen.getByText('-1.20%')).toHaveClass('text-red-600');
  });

  it('shows an empty state when there are no sectors', () => {
    render(<SectorGrid sectors={[]} />);
    expect(screen.getByText('No sector data')).toBeInTheDocument();
  });
});
