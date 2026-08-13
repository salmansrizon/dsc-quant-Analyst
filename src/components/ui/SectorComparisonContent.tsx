import type { SectorComparison } from '../../api/sectorComparison';
import { deltaPercent, deltaVariant } from '../../design/sectorComparisonBadge';
import { Badge } from './Badge';

interface SectorComparisonContentProps {
  /** undefined while loading (or before the zone has ever been opened). */
  data: SectorComparison | undefined;
  loading: boolean;
}

const num = (v: number | null, d = 2) => (v == null ? '—' : v.toFixed(d));

// #92: stock vs its sector's median for P/E, P/B, yield, growth. A metric
// with too few peers still shows the subject's own value — only the
// comparison itself is withheld, never the real computed number (#89's
// "never discard real data" pattern).
export function SectorComparisonContent({ data, loading }: SectorComparisonContentProps) {
  if (loading || !data) {
    return <p className="text-sm text-[var(--text-secondary)]">Loading sector comparison…</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {!data.sector && (
        <p className="text-sm text-[var(--text-secondary)]">
          {data.symbol} isn&apos;t in a known sector — nothing to compare against.
        </p>
      )}
      <ul className="flex flex-col gap-3">
        {data.metrics.map((m) => (
          <li key={m.metric} className="flex items-center justify-between gap-3">
            <span className="text-sm text-[var(--text-primary)]">{m.label}</span>
            <div className="flex items-center gap-2 text-sm">
              <span className="tabular-nums text-[var(--text-primary)]">{num(m.subject_value)}</span>
              {m.comparable && m.subject_value != null && m.sector_median != null ? (
                <>
                  <span className="tabular-nums text-[var(--text-secondary)]">
                    vs {num(m.sector_median)} sector median
                  </span>
                  <Badge variant={deltaVariant(m.metric, m.subject_value, m.sector_median)}>
                    {deltaPercent(m.subject_value, m.sector_median) >= 0 ? '+' : ''}
                    {deltaPercent(m.subject_value, m.sector_median).toFixed(1)}%
                  </Badge>
                </>
              ) : (
                <span className="text-[var(--text-secondary)]">
                  Not enough sector peers to compare ({m.peer_count} found)
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
