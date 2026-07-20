import type { CSSProperties } from 'react';

export interface Finding {
  kind: string;
  severity: 'good' | 'caution' | 'warn';
  headline: string;
  reason: string;
}
export interface Health {
  holdings_valued: number;
  total_value: number;
  is_default_profile: boolean;
  findings: Finding[];
  disclaimer: string;
}

// No Tailwind in this repo (index.css is hand-rolled) — severity colours come
// from the CSS accent vars, inline.
const DOT: Record<Finding['severity'], string> = {
  good: 'var(--accent-green)',
  caution: 'var(--accent-blue)',
  warn: 'var(--accent-red)',
};

const dot = (sev: Finding['severity']): CSSProperties => ({
  width: 10, height: 10, borderRadius: '50%', background: DOT[sev],
  flexShrink: 0, marginTop: 5,
});

/** Portfolio 'health vs your profile' panel (#91). Reads the health block the
 *  #91 backend folds into /portfolio/summary. */
export default function PortfolioHealth({ health }: { health?: Health }) {
  if (!health || health.findings.length === 0) return null;
  return (
    <section className="card" aria-label="Portfolio health">
      <h2 className="text-primary" style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>
        Health vs your profile
      </h2>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {health.findings.map((f) => (
          <li key={f.kind} style={{ display: 'flex', gap: 8 }}>
            <span aria-label={f.severity} title={f.severity} style={dot(f.severity)} />
            <span>
              <strong>{f.headline}</strong>
              <span className="text-secondary" style={{ display: 'block', fontSize: 13 }}>
                {f.reason}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <p className="text-secondary" style={{ fontSize: 11, marginTop: 12 }}>{health.disclaimer}</p>
    </section>
  );
}
