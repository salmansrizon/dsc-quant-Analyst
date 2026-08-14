import * as HoverCard from '@radix-ui/react-hover-card';
import { useState } from 'react';
import type { FitScore } from '../../api/fit';
import { axisBadgeVariant, deriveFitView } from '../../design/fitBucket';
import {
  HOVER_CARD_ARROW_CLASS,
  HOVER_CARD_CLOSE_DELAY,
  HOVER_CARD_CONTENT_CLASS,
  HOVER_CARD_OPEN_DELAY,
} from '../../design/hoverCard';
import { Badge } from './Badge';
import { FitScorecardModal } from './FitScorecardModal';

interface FitScorecardProps {
  /** undefined = not loaded yet (renders nothing); a real FitScore once fetched. */
  fit: FitScore | undefined;
}

// #89: the compact "hover anywhere a stock appears" trigger — stacked chips,
// one per scored axis (never a composite number). Hover opens a summary
// popover with per-axis reasons; click opens the full ScorecardShell in a
// modal. Used identically from Screener, Watchlist, Portfolio, and Stock
// Detail via useFitScores.
export function FitScorecard({ fit }: FitScorecardProps) {
  const [modalOpen, setModalOpen] = useState(false);
  if (!fit) return null;

  const { scoredAxes, muted } = deriveFitView(fit);

  return (
    <>
      <HoverCard.Root openDelay={HOVER_CARD_OPEN_DELAY} closeDelay={HOVER_CARD_CLOSE_DELAY}>
        <HoverCard.Trigger asChild>
          <button
            type="button"
            data-testid="fit-scorecard-trigger"
            aria-label={`Fit scorecard for ${fit.symbol}`}
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-1"
          >
            {scoredAxes.map((axis) => (
              <Badge key={axis.axis} variant={axisBadgeVariant(axis.score as number, muted)}>
                {axis.axis}
              </Badge>
            ))}
            {!fit.scorable && <Badge variant="neutral">Thin data</Badge>}
          </button>
        </HoverCard.Trigger>
        <HoverCard.Portal>
          <HoverCard.Content side="top" sideOffset={6} className={HOVER_CARD_CONTENT_CLASS}>
            {muted && (
              <p className="mb-2 text-xs text-[var(--text-secondary)]">
                Complete your profile to personalize this.
              </p>
            )}
            <ul className="flex flex-col gap-1.5">
              {scoredAxes.map((axis) => (
                <li key={axis.axis}>
                  <span className="font-medium">{axis.axis}:</span> {axis.reason}
                </li>
              ))}
              {!fit.scorable && (
                <li className="text-[var(--text-secondary)]">
                  Not enough data for a full picture.
                </li>
              )}
            </ul>
            <HoverCard.Arrow className={HOVER_CARD_ARROW_CLASS} />
          </HoverCard.Content>
        </HoverCard.Portal>
      </HoverCard.Root>
      <FitScorecardModal fit={fit} open={modalOpen} onOpenChange={setModalOpen} />
    </>
  );
}
