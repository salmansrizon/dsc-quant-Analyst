import type { ReactNode } from 'react';
import { getZoneConfig, type ZoneType } from '../../design/zones';
import { Card } from './Card';

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
  const config = getZoneConfig(type);
  const { Icon } = config;
  return (
    <Card revealIndex={revealIndex} testId={`zone-${type}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon size={16} style={{ color: config.colorVar }} />
          <span className="text-sm font-semibold" style={{ color: config.colorVar }}>
            {config.label}
          </span>
        </div>
        {actions}
      </div>
      {children}
    </Card>
  );
}
