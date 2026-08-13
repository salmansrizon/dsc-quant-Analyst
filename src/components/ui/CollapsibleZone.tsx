import * as Collapsible from '@radix-ui/react-collapsible';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { getZoneConfig, type ZoneType } from '../../design/zones';
import { CARD_BASE_CLASS } from './Card';

interface CollapsibleZoneProps {
  type: ZoneType;
  defaultOpen?: boolean;
  children: ReactNode;
}

// #90: the progressive-disclosure form of a Zone card — used for Fundamentals
// and the Sector-comparison placeholder on Stock Detail, where the ticket
// wants the dense, long-tail data collapsed by default. The whole header row
// is the toggle (not a separate hidden control). Shares Card's exact styling
// (CARD_BASE_CLASS) but can't compose <Card> directly, since Radix's
// Collapsible.Trigger must be the outer clickable element, not a div.
export function CollapsibleZone({ type, defaultOpen = false, children }: CollapsibleZoneProps) {
  const [open, setOpen] = useState(defaultOpen);
  const config = getZoneConfig(type);
  const { Icon } = config;

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className={CARD_BASE_CLASS}>
      <Collapsible.Trigger className="flex w-full items-center justify-between gap-2 p-5 text-left">
        <div className="flex items-center gap-2">
          <Icon size={16} style={{ color: config.colorVar }} />
          <span className="text-sm font-semibold" style={{ color: config.colorVar }}>
            {config.label}
          </span>
        </div>
        <ChevronDown
          size={16}
          className={`text-[var(--text-secondary)] transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </Collapsible.Trigger>
      <Collapsible.Content className="px-5 pb-5">{children}</Collapsible.Content>
    </Collapsible.Root>
  );
}
