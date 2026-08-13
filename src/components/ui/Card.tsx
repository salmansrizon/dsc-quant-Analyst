import { motion } from 'motion/react';
import type { CSSProperties, MouseEventHandler, ReactNode } from 'react';
import { cardHover, zoneReveal } from '../../design/motion';

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
  const classes =
    `rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5 ${className}`.trim();

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
