import type { FitAxis, FitScore } from '../api/fit';
import type { BadgeVariant } from '../components/ui/Badge';

export type FitBucket = 'positive' | 'neutral' | 'negative';

// #89: sector-percentile axis scores (0..100) bucketed into three bands for
// chip/badge coloring. Terciles — the fit engine only promises "higher =
// better" with no finer guidance, so an even split is the honest default.
export function bucketAxisScore(score: number): FitBucket {
  if (score >= 66) return 'positive';
  if (score >= 34) return 'neutral';
  return 'negative';
}

// A default-profile score isn't personalized to this user yet, so it's always
// muted regardless of the bucket (#87/#89 incomplete-profile decision).
export function axisBadgeVariant(score: number, isDefaultProfile: boolean): BadgeVariant {
  if (isDefaultProfile) return 'neutral';
  return bucketAxisScore(score);
}

export interface FitView {
  /** Axes that actually scored — null-score axes are dropped, never faked. */
  scoredAxes: FitAxis[];
  /** True when the score is against the neutral cold-start profile, not a
   * personalized one — chips/badges render muted regardless of bucket. */
  muted: boolean;
}

// Shared by FitScorecard (compact trigger) and FitScorecardModal (full view)
// so the two can't drift on what counts as "scored" or "muted".
export function deriveFitView(fit: FitScore): FitView {
  return {
    scoredAxes: fit.axes.filter((a) => a.score != null),
    muted: fit.is_default_profile,
  };
}
