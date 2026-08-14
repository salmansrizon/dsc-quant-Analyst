import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { FitScore } from '../../api/fit';
import { FitScorecardContent } from './FitScorecardContent';

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
          <FitScorecardContent fit={fit} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
