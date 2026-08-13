import type { ReactNode } from 'react';

export type BadgeVariant = 'positive' | 'negative' | 'neutral' | 'warning';

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
