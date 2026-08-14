import { describe, expect, it } from 'vitest';
import { MOTION_DURATION, pageTransition, zoneReveal } from '../motion';

// #87 decision: motion is scoped and bounded, not decorative. This is a
// regression guard on that budget, not just a shape check.
const PERFORMANCE_BUDGET_S = 0.5;

describe('motion presets (#87)', () => {
  it('keeps every duration within the tasteful/performance budget', () => {
    Object.values(MOTION_DURATION).forEach((seconds) => {
      expect(seconds).toBeGreaterThan(0);
      expect(seconds).toBeLessThanOrEqual(PERFORMANCE_BUDGET_S);
    });
  });

  it('fades page transitions in and out without motion (opacity only)', () => {
    expect(pageTransition.initial).toMatchObject({ opacity: 0 });
    expect(pageTransition.animate).toMatchObject({ opacity: 1 });
    expect(pageTransition.exit).toMatchObject({ opacity: 0 });
  });

  it('staggers zone reveal by index so cards don\'t all pop at once', () => {
    const first = zoneReveal.visible as (i: number) => Record<string, unknown>;
    const at0 = first(0) as { transition: { delay: number } };
    const at2 = first(2) as { transition: { delay: number } };
    expect(at2.transition.delay).toBeGreaterThan(at0.transition.delay);
  });
});
