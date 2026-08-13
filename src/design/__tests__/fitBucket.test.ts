import { describe, expect, it } from 'vitest';
import { axisBadgeVariant, bucketAxisScore, deriveFitView } from '../fitBucket';
import type { FitScore } from '../../api/fit';

describe('bucketAxisScore', () => {
  it('buckets the top tercile as positive', () => {
    expect(bucketAxisScore(100)).toBe('positive');
    expect(bucketAxisScore(66)).toBe('positive');
  });

  it('buckets the middle tercile as neutral', () => {
    expect(bucketAxisScore(65.9)).toBe('neutral');
    expect(bucketAxisScore(34)).toBe('neutral');
  });

  it('buckets the bottom tercile as negative', () => {
    expect(bucketAxisScore(33.9)).toBe('negative');
    expect(bucketAxisScore(0)).toBe('negative');
  });
});

describe('axisBadgeVariant', () => {
  it('follows the score bucket for a real (non-default) profile', () => {
    expect(axisBadgeVariant(80, false)).toBe('positive');
    expect(axisBadgeVariant(50, false)).toBe('neutral');
    expect(axisBadgeVariant(10, false)).toBe('negative');
  });

  it('is always muted (neutral) on a default profile, regardless of score', () => {
    expect(axisBadgeVariant(95, true)).toBe('neutral');
    expect(axisBadgeVariant(5, true)).toBe('neutral');
  });
});

describe('deriveFitView', () => {
  function baseFit(overrides: Partial<FitScore> = {}): FitScore {
    return {
      symbol: 'GP',
      composite: 70,
      scorable: true,
      weight_caption: '',
      axes: [
        { axis: 'Value', score: 80, reason: 'r1', weight: 0.2 },
        { axis: 'Growth', score: null, reason: 'no data', weight: 0 },
      ],
      is_default_profile: false,
      disclaimer: 'd',
      ...overrides,
    };
  }

  it('drops null-score axes and is not muted for a real profile', () => {
    const view = deriveFitView(baseFit());
    expect(view.scoredAxes.map((a) => a.axis)).toEqual(['Value']);
    expect(view.muted).toBe(false);
  });

  it('is muted on a default profile', () => {
    const view = deriveFitView(baseFit({ is_default_profile: true }));
    expect(view.muted).toBe(true);
  });
});
