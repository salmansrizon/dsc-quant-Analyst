import type { TargetAndTransition, Transition, Variants } from 'motion/react';

// #87 decision: motion is scoped to four triggers only — theme/route
// transitions, zone/scorecard reveal-on-mount, hover micro-interactions, and
// price-number count-up (src/hooks/useCountUp.ts). No decorative auto-play,
// no motion on static data tables. Durations stay short (perf budget).
export const MOTION_DURATION = {
  fast: 0.15,
  base: 0.25,
  slow: 0.4,
} as const;

const EASE_OUT = 'easeOut' as const;

export const pageTransition: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: MOTION_DURATION.base, ease: EASE_OUT } },
  exit: { opacity: 0, transition: { duration: MOTION_DURATION.fast, ease: EASE_OUT } },
};

// Reveal-on-mount for zone cards / scorecard axes. Pass the item's index as
// the `custom` prop so a list staggers instead of popping in all at once.
export const zoneReveal: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: (index: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: MOTION_DURATION.base, delay: index * 0.05, ease: EASE_OUT },
  }),
};

const hoverTransition: Transition = { duration: MOTION_DURATION.fast, ease: EASE_OUT };

// Spread onto a motion component: <motion.div {...cardHover}>
export const cardHover: { whileHover: TargetAndTransition } = {
  whileHover: { y: -2, transition: hoverTransition },
};
