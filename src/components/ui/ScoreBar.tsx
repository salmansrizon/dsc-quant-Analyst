import { VARIANT_COLOR_VAR, type BadgeVariant } from './Badge';

interface ScoreBarProps {
  score: number;
  variant?: BadgeVariant;
}

// #90: the Fit-for-you zone's signature element — a small horizontal meter
// per axis, encoding the same 0..100 score the chip color already implies,
// so the leading zone reads as a real scorecard rather than a bare list.
export function ScoreBar({ score, variant = 'neutral' }: ScoreBarProps) {
  const clamped = Math.min(Math.max(score, 0), 100);
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--border-color)]"
    >
      <div
        data-testid="score-bar-fill"
        className="h-full rounded-full"
        style={{ width: `${clamped}%`, background: VARIANT_COLOR_VAR[variant] }}
      />
    </div>
  );
}
