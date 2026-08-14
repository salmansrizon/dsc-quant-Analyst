import { describe, expect, it } from 'vitest';
import { easeOutCubic, interpolateCountUp } from '../countUp';

describe('easeOutCubic', () => {
  it('starts at 0 and ends at 1', () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
  });

  it('is monotonically increasing', () => {
    const samples = [0, 0.2, 0.4, 0.6, 0.8, 1].map(easeOutCubic);
    for (let i = 1; i < samples.length; i++) {
      expect(samples[i]).toBeGreaterThan(samples[i - 1]);
    }
  });
});

describe('interpolateCountUp', () => {
  it('returns the start value at progress 0 and the end value at progress 1', () => {
    expect(interpolateCountUp(10, 50, 0)).toBe(10);
    expect(interpolateCountUp(10, 50, 1)).toBe(50);
  });

  it('clamps progress outside [0, 1]', () => {
    expect(interpolateCountUp(10, 50, -0.5)).toBe(10);
    expect(interpolateCountUp(10, 50, 1.5)).toBe(50);
  });

  it('works for decreasing values (a price drop)', () => {
    expect(interpolateCountUp(50, 10, 0)).toBe(50);
    expect(interpolateCountUp(50, 10, 1)).toBe(10);
    const mid = interpolateCountUp(50, 10, 0.5);
    expect(mid).toBeLessThan(50);
    expect(mid).toBeGreaterThan(10);
  });
});
