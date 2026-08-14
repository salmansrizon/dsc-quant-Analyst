import type { FindingSeverity, PortfolioFinding, PortfolioHealth } from '../../api/portfolioHealth';
import { Badge, type BadgeVariant } from './Badge';

const SEVERITY_VARIANT: Record<FindingSeverity, BadgeVariant> = {
  good: 'positive',
  caution: 'warning',
  warn: 'negative',
};

const SEVERITY_LABEL: Record<FindingSeverity, string> = {
  good: 'Good',
  caution: 'Caution',
  warn: 'Warn',
};

function FindingRow({ finding }: { finding: PortfolioFinding }) {
  return (
    <li className="flex flex-col gap-1 border-b border-[var(--border-color)] py-3 last:border-0">
      <div className="flex items-center gap-2">
        <Badge variant={SEVERITY_VARIANT[finding.severity]}>{SEVERITY_LABEL[finding.severity]}</Badge>
        <span className="text-sm font-semibold text-[var(--text-primary)]">{finding.headline}</span>
      </div>
      <p className="text-xs text-[var(--text-secondary)]">{finding.reason}</p>
    </li>
  );
}

// #97: wires up #91's portfolio-health findings — observations only, never
// advice (the actionable nudges for the same signals live in #93/the feed).
export function PortfolioHealthContent({ health }: { health: PortfolioHealth }) {
  return (
    <div>
      {health.is_default_profile && (
        <p className="mb-3 text-xs text-[var(--text-secondary)]">
          Complete your profile to personalize these observations.
        </p>
      )}
      {health.findings.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">No notable observations yet.</p>
      ) : (
        <ul>
          {health.findings.map((f) => (
            <FindingRow key={f.kind} finding={f} />
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-col gap-1 text-xs text-[var(--text-secondary)]">
        {health.unweighted && (
          <p>Some holdings couldn't be priced — these observations use equal weighting instead.</p>
        )}
        <p>{health.disclaimer}</p>
      </div>
    </div>
  );
}
