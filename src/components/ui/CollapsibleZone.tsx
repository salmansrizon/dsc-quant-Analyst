import * as Collapsible from '@radix-ui/react-collapsible';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import type { ReactNode } from 'react';
import type { ZoneType } from '../../design/zones';
import { CARD_BASE_CLASS } from './Card';
import { ZoneHeader } from './ZoneHeader';

interface CollapsibleZoneProps {
  type: ZoneType;
  defaultOpen?: boolean;
  children: ReactNode;
  /** #92: lets a parent lazy-fetch data on first expand instead of on mount. */
  onOpenChange?: (open: boolean) => void;
}

// #90: the progressive-disclosure form of a Zone card — used for Fundamentals
// and the Sector-comparison placeholder on Stock Detail, where the ticket
// wants the dense, long-tail data collapsed by default. The whole header row
// is the toggle (not a separate hidden control). Shares Card's exact styling
// (CARD_BASE_CLASS) and Zone's header (ZoneHeader) but can't compose <Card>/
// <Zone> directly, since Radix's Collapsible.Trigger must be the outer
// clickable element, not a div — and unlike Zone, has no `actions` slot:
// nesting another interactive control inside the Trigger button would be
// invalid HTML and would toggle the collapse on every click.
export function CollapsibleZone({
  type,
  defaultOpen = false,
  children,
  onOpenChange,
}: CollapsibleZoneProps) {
  const [open, setOpen] = useState(defaultOpen);

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    onOpenChange?.(next);
  };

  return (
    <Collapsible.Root open={open} onOpenChange={handleOpenChange} className={CARD_BASE_CLASS}>
      <Collapsible.Trigger className="flex w-full items-center justify-between gap-2 p-5 text-left">
        <ZoneHeader type={type} />
        <ChevronDown
          size={16}
          className={`text-[var(--text-secondary)] transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </Collapsible.Trigger>
      <Collapsible.Content className="px-5 pb-5">{children}</Collapsible.Content>
    </Collapsible.Root>
  );
}
