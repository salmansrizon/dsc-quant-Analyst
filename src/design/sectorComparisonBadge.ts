import type { BadgeVariant } from '../components/ui/Badge';
import type { SectorComparisonMetric } from '../api/sectorComparison';

// #92: which direction is favorable per metric — fixed domain knowledge, the
// same for every symbol/sector, so it lives as a constant rather than
// backend-computed data (unlike per-axis fit scores, which vary per subject).
//
// Mirrors backend/fit_engine.py's `invert` argument to _metric_axis/
// _value_axis (pe/pb: invert=True, yield/growth: invert=False) — that's the
// same "which direction scores higher" fact, encoded separately here since
// the sector-comparison response carries raw values, not the engine's
// percentile scores. If fit_engine.py's directions ever change, update here.
const FAVORABLE_DIRECTION: Record<SectorComparisonMetric['metric'], 'lower' | 'higher'> = {
  pe: 'lower',
  pb: 'lower',
  yield: 'higher',
  growth: 'higher',
};

// Color the delta by whether the subject sits on the favorable side of the
// sector median for that specific metric — a factual observation (#91's
// pattern for objective peer/portfolio findings), never advice framing.
export function deltaVariant(
  metric: SectorComparisonMetric['metric'],
  subjectValue: number,
  sectorMedian: number,
): BadgeVariant {
  if (subjectValue === sectorMedian) return 'neutral';
  const isLower = subjectValue < sectorMedian;
  const favorable = FAVORABLE_DIRECTION[metric] === 'lower' ? isLower : !isLower;
  return favorable ? 'positive' : 'negative';
}

export function deltaPercent(subjectValue: number, sectorMedian: number): number {
  if (sectorMedian === 0) return 0;
  return ((subjectValue - sectorMedian) / Math.abs(sectorMedian)) * 100;
}
