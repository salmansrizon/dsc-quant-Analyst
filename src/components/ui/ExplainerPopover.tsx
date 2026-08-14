import * as HoverCard from '@radix-ui/react-hover-card';
import { CircleHelp } from 'lucide-react';
import type { ReactNode } from 'react';
import {
  HOVER_CARD_ARROW_CLASS,
  HOVER_CARD_CLOSE_DELAY,
  HOVER_CARD_CONTENT_CLASS,
  HOVER_CARD_OPEN_DELAY,
} from '../../design/hoverCard';

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
    <HoverCard.Root openDelay={HOVER_CARD_OPEN_DELAY} closeDelay={HOVER_CARD_CLOSE_DELAY}>
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
        <HoverCard.Content side="top" sideOffset={6} className={HOVER_CARD_CONTENT_CLASS}>
          {children}
          <HoverCard.Arrow className={HOVER_CARD_ARROW_CLASS} />
        </HoverCard.Content>
      </HoverCard.Portal>
    </HoverCard.Root>
  );
}
