import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { FitScore } from '../../api/fit';
import { axisBadgeVariant, deriveFitView } from '../../design/fitBucket';
import { ScorecardShell, type ScorecardAxis } from './ScorecardShell';

interface FitScorecardModalProps {
  fit: FitScore;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// #89: "click -> full view" from the compact FitScorecard trigger. A modal
// rather than a page section, so it works everywhere the chips render
// (screener row, watchlist, portfolio, detail) without depending on #90's
// Stock Detail zone layout.
export function FitScorecardModal({ fit, open, onOpenChange }: FitScorecardModalProps) {
  const { scoredAxes, muted } = deriveFitView(fit);

  const axes: ScorecardAxis[] = scoredAxes.map((axis) => ({
    key: axis.axis,
    label: axis.axis,
    reason: axis.reason,
    badgeLabel: String(Math.round(axis.score as number)),
    badgeVariant: axisBadgeVariant(axis.score as number, muted),
  }));

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 focus:outline-none"
          aria-describedby={undefined}
        >
          <Dialog.Title className="sr-only">Fit scorecard for {fit.symbol}</Dialog.Title>
          <Dialog.Close
            aria-label="Close"
            className="absolute right-2 top-2 z-10 rounded-full p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            <X size={16} />
          </Dialog.Close>
          <ScorecardShell
            axes={axes}
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
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
