import type { FitScore } from '../../api/fit';
import { axisBadgeVariant, deriveFitView } from '../../design/fitBucket';
import { ScoreBar } from './ScoreBar';
import { ScorecardShell, type ScorecardAxis } from './ScorecardShell';

interface FitScorecardContentProps {
  fit: FitScore;
  revealIndex?: number;
}

// The full scorecard body — axes with reasons/badges/ScoreBar meters, the
// default-profile prompt, weight caption, thin-data note, and disclaimer.
// Shared by #89's FitScorecardModal (inside a Dialog) and #90's inline
// Fit-for-you zone on Stock Detail (directly on the page) so the two can't
// drift on what "the full scorecard" actually shows.
export function FitScorecardContent({ fit, revealIndex }: FitScorecardContentProps) {
  const { scoredAxes, muted } = deriveFitView(fit);

  const axes: ScorecardAxis[] = scoredAxes.map((axis) => {
    const score = axis.score as number;
    const variant = axisBadgeVariant(score, muted);
    return {
      key: axis.axis,
      label: axis.axis,
      reason: axis.reason,
      badgeLabel: String(Math.round(score)),
      badgeVariant: variant,
      value: <ScoreBar score={score} variant={variant} />,
    };
  });

  return (
    <ScorecardShell
      axes={axes}
      revealIndex={revealIndex}
      header={
        muted && (
          <p className="mb-3 text-xs text-[var(--text-secondary)]">
            Complete your profile to personalize this scorecard.
          </p>
        )
      }
      footer={
        <div className="mt-3 flex flex-col gap-1 text-xs text-[var(--text-secondary)]">
          {fit.weight_caption && <p>{fit.weight_caption}</p>}
          {!fit.scorable && <p>Not enough data for a full picture yet.</p>}
          <p>{fit.disclaimer}</p>
        </div>
      }
    />
  );
}
