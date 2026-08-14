import { motion } from 'motion/react';
import type { CSSProperties, MouseEventHandler, ReactNode } from 'react';
import { cardHover, zoneReveal } from '../../design/motion';

// Shared with CollapsibleZone, which can't compose <Card> directly (Radix's
// Collapsible.Trigger must be the outer clickable element, not a div), but
// should still look like one rather than re-typing this string by hand.
export const CARD_BASE_CLASS =
  'rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]';

interface CardProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  onClick?: MouseEventHandler<HTMLDivElement>;
  testId?: string;
  /** Reveal-on-mount stagger index; omit to render statically (no motion). */
  revealIndex?: number;
  hoverLift?: boolean;
}

export function Card({
  children,
  className = '',
  style,
  onClick,
  testId,
  revealIndex,
  hoverLift = true,
}: CardProps) {
  const classes = `${CARD_BASE_CLASS} p-5 ${className}`.trim();

  if (revealIndex === undefined) {
    return (
      <div className={classes} style={style} onClick={onClick} data-testid={testId}>
        {children}
      </div>
    );
  }

  return (
    <motion.div
      className={classes}
      style={style}
      onClick={onClick}
      data-testid={testId}
      variants={zoneReveal}
      custom={revealIndex}
      initial="hidden"
      animate="visible"
      whileHover={hoverLift ? cardHover.whileHover : undefined}
    >
      {children}
    </motion.div>
  );
}
