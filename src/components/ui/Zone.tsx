import type { ReactNode } from 'react';
import type { ZoneType } from '../../design/zones';
import { Card } from './Card';
import { ZoneHeader } from './ZoneHeader';

interface ZoneProps {
  type: ZoneType;
  children: ReactNode;
  revealIndex?: number;
  actions?: ReactNode;
}

// The typed card shell for the #87 zone vocabulary — every Stock Detail (#90)
// / Dashboard (#96) section renders through one of these instead of a bespoke
// per-page layout.
export function Zone({ type, children, revealIndex, actions }: ZoneProps) {
  return (
    <Card revealIndex={revealIndex} testId={`zone-${type}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <ZoneHeader type={type} />
        {actions}
      </div>
      {children}
    </Card>
  );
}
