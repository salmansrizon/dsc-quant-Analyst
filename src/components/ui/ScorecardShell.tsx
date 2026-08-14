import type { ReactNode } from 'react';
import { Badge, type BadgeVariant } from './Badge';
import { ExplainerPopover } from './ExplainerPopover';
import { Zone } from './Zone';

export interface ScorecardAxis {
  key: string;
  label: string;
  /** Required — every axis ships a human-readable reason (map #84's
   * non-negotiable explainability rule), never a bare score. */
  reason: string;
  badgeLabel?: string;
  badgeVariant?: BadgeVariant;
  value?: ReactNode;
}

interface ScorecardShellProps {
  axes: ScorecardAxis[];
  revealIndex?: number;
  /** Renders above the axes list — e.g. #89's "complete your profile" prompt
   * on a default-profile scorecard, which must precede the axes, not follow. */
  header?: ReactNode;
  footer?: ReactNode;
}

// The presentational shell for the Fit Scorecard — #89 supplies the real
// fit-engine axes; this only defines the layout, the explainer wiring, and
// the badge/value slots.
export function ScorecardShell({ axes, revealIndex, header, footer }: ScorecardShellProps) {
  return (
    <Zone type="fit" revealIndex={revealIndex}>
      {header}
      <ul className="flex flex-col gap-3">
        {axes.map((axis) => (
          <li key={axis.key} className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-[var(--text-primary)]">{axis.label}</span>
              <ExplainerPopover>{axis.reason}</ExplainerPopover>
            </div>
            <div className="flex items-center gap-2">
              {axis.value}
              {axis.badgeLabel && <Badge variant={axis.badgeVariant}>{axis.badgeLabel}</Badge>}
            </div>
          </li>
        ))}
      </ul>
      {footer}
    </Zone>
  );
}
