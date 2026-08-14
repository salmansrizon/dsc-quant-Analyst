import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SectorComparisonContent } from '../SectorComparisonContent';
import type { SectorComparison } from '../../../api/sectorComparison';

describe('SectorComparisonContent', () => {
  it('shows a loading state while data has not arrived', () => {
    render(<SectorComparisonContent data={undefined} loading />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders a comparable metric with its value, sector median, and delta', () => {
    const data: SectorComparison = {
      symbol: 'GP',
      sector: 'Telecom',
      metrics: [
        { metric: 'pe', label: 'P/E', subject_value: 10, sector_median: 16, peer_count: 5, comparable: true },
      ],
    };
    render(<SectorComparisonContent data={data} loading={false} />);
    expect(screen.getByText('P/E')).toBeInTheDocument();
    expect(screen.getByText('10.00')).toBeInTheDocument();
    expect(screen.getByText(/16\.00/)).toBeInTheDocument();
    expect(screen.getByText(/-37\.5%/)).toBeInTheDocument();
  });

  it('still shows the subject\'s own value for a non-comparable metric, alongside a not-enough-peers note', () => {
    const data: SectorComparison = {
      symbol: 'GP',
      sector: 'Telecom',
      metrics: [
        { metric: 'pe', label: 'P/E', subject_value: 10, sector_median: null, peer_count: 2, comparable: false },
        { metric: 'pb', label: 'P/B', subject_value: 1.2, sector_median: 2.0, peer_count: 5, comparable: true },
      ],
    };
    render(<SectorComparisonContent data={data} loading={false} />);
    expect(screen.getByText('P/E')).toBeInTheDocument();
    expect(screen.getByText('10.00')).toBeInTheDocument();
    expect(screen.getByText(/not enough sector peers/i)).toBeInTheDocument();
    expect(screen.getByText('P/B')).toBeInTheDocument();
    expect(screen.getByText('1.20')).toBeInTheDocument();
  });

  it('notes when the stock has no known sector', () => {
    const data: SectorComparison = {
      symbol: 'GP',
      sector: null,
      metrics: [
        { metric: 'pe', label: 'P/E', subject_value: null, sector_median: null, peer_count: 0, comparable: false },
        { metric: 'pb', label: 'P/B', subject_value: null, sector_median: null, peer_count: 0, comparable: false },
        { metric: 'yield', label: 'Dividend Yield %', subject_value: null, sector_median: null, peer_count: 0, comparable: false },
        { metric: 'growth', label: 'EPS Growth %/yr', subject_value: null, sector_median: null, peer_count: 0, comparable: false },
      ],
    };
    render(<SectorComparisonContent data={data} loading={false} />);
    expect(screen.getByText(/isn't in a known sector/i)).toBeInTheDocument();
  });
});
