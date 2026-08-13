import { describe, expect, it } from 'vitest';
import { deltaPercent, deltaVariant } from '../sectorComparisonBadge';

describe('deltaVariant', () => {
  it('is positive when a lower-is-better metric (P/E) sits below the sector median', () => {
    expect(deltaVariant('pe', 10, 16)).toBe('positive');
  });

  it('is negative when a lower-is-better metric (P/E) sits above the sector median', () => {
    expect(deltaVariant('pe', 20, 16)).toBe('negative');
  });

  it('is positive when a higher-is-better metric (yield) sits above the sector median', () => {
    expect(deltaVariant('yield', 9, 6)).toBe('positive');
  });

  it('is negative when a higher-is-better metric (growth) sits below the sector median', () => {
    expect(deltaVariant('growth', 2, 8)).toBe('negative');
  });

  it('is neutral when the subject exactly matches the sector median', () => {
    expect(deltaVariant('pe', 16, 16)).toBe('neutral');
  });

  it('applies the same lower-is-better rule to P/B', () => {
    expect(deltaVariant('pb', 1.2, 2.0)).toBe('positive');
    expect(deltaVariant('pb', 3.0, 2.0)).toBe('negative');
  });
});

describe('deltaPercent', () => {
  it('computes the signed percent difference from the sector median', () => {
    expect(deltaPercent(18, 16)).toBeCloseTo(12.5);
    expect(deltaPercent(12, 16)).toBeCloseTo(-25);
  });

  it('returns 0 when the sector median is 0 (avoids divide-by-zero)', () => {
    expect(deltaPercent(5, 0)).toBe(0);
  });
});
