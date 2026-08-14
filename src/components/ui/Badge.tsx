import type { ReactNode } from 'react';

export type BadgeVariant = 'positive' | 'negative' | 'neutral' | 'warning';

// The canonical variant -> token color. Shared with ScoreBar, which needs a
// raw var() string for an inline style rather than a Tailwind class.
//
// VARIANT_STYLE below can't be *derived* from this map — Tailwind's build-time
// scanner needs each class as a literal, grep-able string in source, so
// constructing `bg-[${...}]` dynamically would silently fail to compile. Keep
// the two in sync by hand; VARIANT_COLOR_VAR is still the single import site
// for anything that isn't emitting a Tailwind class (ScoreBar, inline styles).
export const VARIANT_COLOR_VAR: Record<BadgeVariant, string> = {
  positive: 'var(--accent-green)',
  negative: 'var(--accent-red)',
  neutral: 'var(--text-secondary)',
  warning: 'var(--zone-sector)',
};

const VARIANT_STYLE: Record<BadgeVariant, string> = {
  positive: 'bg-[var(--accent-green)]/15 text-[var(--accent-green)]',
  negative: 'bg-[var(--accent-red)]/15 text-[var(--accent-red)]',
  neutral: 'bg-[var(--text-secondary)]/15 text-[var(--text-secondary)]',
  warning: 'bg-[var(--zone-sector)]/15 text-[var(--zone-sector)]',
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
}

export function Badge({ variant = 'neutral', children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${VARIANT_STYLE[variant]}`}
    >
      {children}
    </span>
  );
}
