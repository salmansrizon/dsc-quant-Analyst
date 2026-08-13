import * as HoverCard from '@radix-ui/react-hover-card';
import { CircleHelp } from 'lucide-react';
import type { ReactNode } from 'react';

interface ExplainerPopoverProps {
  /** The reason string — must always be human-readable, per the map's
   * explainability rule (never a bare score or "buy this"). */
  children: ReactNode;
  label?: string;
}

// #87's "hover-popover" primitive: a small "what does this mean?" affordance
// for derived/computed values (fit axes, indicators, recommendations). Raw
// market data doesn't get one — see #87's microcopy-scope decision.
export function ExplainerPopover({ children, label = 'What does this mean?' }: ExplainerPopoverProps) {
  return (
    <HoverCard.Root openDelay={150} closeDelay={100}>
      <HoverCard.Trigger asChild>
        <button
          type="button"
          aria-label={label}
          className="inline-flex items-center justify-center rounded-full text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
        >
          <CircleHelp size={14} />
        </button>
      </HoverCard.Trigger>
      <HoverCard.Portal>
        <HoverCard.Content
          side="top"
          sideOffset={6}
          className="max-w-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--text-primary)] shadow-[var(--shadow-elevated)]"
        >
          {children}
          <HoverCard.Arrow className="fill-[var(--bg-elevated)]" />
        </HoverCard.Content>
      </HoverCard.Portal>
    </HoverCard.Root>
  );
}
