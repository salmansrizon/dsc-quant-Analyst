import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';
import apiClient from '../api/client';
import { colors } from '../design';

const StatCard = ({ label, value, sub }) => (
  <div className="stat-card" style={{ flex: 1 }}>
    <div style={{ color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.1, fontWeight: 500 }}>
      {label}
    </div>
    <div style={{ color: colors.textPrimary, fontSize: 26, fontWeight: 700, marginTop: 10, lineHeight: 1, fontVariantNumeric: 'tabular-nums', letterSpacing: -0.5 }}>
      {value ?? '—'}
    </div>
    {sub && <div style={{ color: colors.textSecondary, fontSize: 11, marginTop: 6 }}>{sub}</div>}
  </div>
);

const SkeletonCard = () => (
  <div className="stat-card" style={{ flex: 1 }}>
    <div className="skeleton" style={{ height: 11, width: '55%', marginBottom: 12 }} />
    <div className="skeleton" style={{ height: 26, width: '75%' }} />
  </div>
);

const SectorRow = ({ sector }) => {
  const change = parseFloat(sector.avg_change ?? 0);
  const positive = change >= 0;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', padding: '9px 0',
      borderBottom: `1px solid ${colors.border}`, gap: 8,
    }}>
      <span style={{ color: colors.textPrimary, fontSize: 13, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {sector.Sector}
      </span>
      <span style={{ color: colors.textSecondary, fontSize: 11, flexShrink: 0 }}>
        {sector.stock_count}
      </span>
      <span className={`ds-badge ${positive ? 'ds-badge-green' : 'ds-badge-red'}`}>
        {positive
          ? <TrendingUp size={10} aria-hidden="true" />
          : <TrendingDown size={10} aria-hidden="true" />}
        {positive ? '+' : ''}{change.toFixed(2)}%
      </span>
    </div>
  );
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div style={{
      background: colors.surface2, border: `1px solid ${colors.border}`,
      borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: 'var(--shadow-md)',
    }}>
      <div style={{ color: colors.textSecondary, marginBottom: 4 }}>{label}</div>
      <div style={{ color: d.fill, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
        ৳{Number(d.value).toLocaleString(undefined, { minimumFractionDigits: 2 })}
      </div>
    </div>
  );
};

export const DashboardPage = () => {
  const [summary, setSummary] = useState(null);
  const [sectors, setSectors] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiClient.get('/market/summary').catch(() => null),
      apiClient.get('/market/sectors').catch(() => []),
      apiClient.get('/portfolio').catch(() => []),
    ]).then(([s, sec, port]) => {
      setSummary(s);
      setSectors(Array.isArray(sec) ? sec : []);
      setPortfolio(Array.isArray(port) ? port : []);
      setLoading(false);
    });
  }, []);

  const chartData = portfolio.slice(0, 8).map(p => ({
    symbol: p.symbol,
    value: (p.current_price ?? p.buy_price) * p.quantity,
    pnl: p.pnl ?? 0,
  }));

  if (loading) return (
    <div style={{ display: 'flex', gap: 16, height: '100%' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
        </div>
        <div className="ds-card" style={{ flex: 1, padding: 20 }}>
          <div className="skeleton" style={{ height: 11, width: '28%', marginBottom: 18 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      </div>
      <div className="ds-card" style={{ width: 280, padding: 16 }}>
        <div className="skeleton" style={{ height: 11, width: '40%', marginBottom: 18 }} />
        {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton" style={{ height: 32, marginBottom: 8 }} />)}
      </div>
    </div>
  );

  return (
    <div style={{ display: 'flex', gap: 16, height: '100%' }}>
      {/* Left panel */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
        {/* Stat cards */}
        <div style={{ display: 'flex', gap: 12 }}>
          <StatCard label="Total Stocks" value={summary?.total_stocks} />
          <StatCard label="Sectors" value={summary?.total_sectors} />
          <StatCard
            label="Avg Price"
            value={summary?.avg_price != null ? `৳${parseFloat(summary.avg_price).toFixed(2)}` : '—'}
          />
          <StatCard
            label="Turnover"
            value={summary?.total_turnover != null ? `৳${(parseFloat(summary.total_turnover) / 1e7).toFixed(1)}Cr` : '—'}
            sub={summary?.last_updated ? `Updated ${summary.last_updated}` : null}
          />
        </div>

        {/* Holdings chart */}
        <div className="ds-card" style={{ flex: 1, padding: 20, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <div>
              <div style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 600 }}>Top Holdings</div>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 2 }}>Portfolio value by position</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: colors.textSecondary }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--color-green)', display: 'inline-block' }} />
                Gain
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--color-red)', display: 'inline-block' }} />
                Loss
              </span>
            </div>
          </div>

          {chartData.length > 0 ? (
            <div style={{ flex: 1, minHeight: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} barCategoryGap="32%">
                  <XAxis
                    dataKey="symbol"
                    tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }}
                    axisLine={false} tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }}
                    axisLine={false} tickLine={false}
                    tickFormatter={v => `৳${(v/1000).toFixed(0)}k`}
                    width={52}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--color-accent-subtle)' }} />
                  <Bar dataKey="value" radius={[5, 5, 0, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={entry.pnl >= 0 ? 'var(--color-green)' : 'var(--color-red)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              <PieChart size={32} color="var(--color-border)" />
              <div style={{ color: colors.textSecondary, fontSize: 13 }}>Add stocks to see your portfolio chart</div>
            </div>
          )}
        </div>
      </div>

      {/* Right panel — Sectors */}
      <div className="ds-card" style={{ width: 268, padding: 16, overflowY: 'auto', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
        <div style={{ marginBottom: 14 }}>
          <div style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 600 }}>Sectors</div>
          <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 2 }}>Market overview</div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 4, paddingBottom: 6, borderBottom: `1px solid ${colors.border}` }}>
          <span>Sector</span>
          <span>Stocks &nbsp; Chg</span>
        </div>
        {sectors.length > 0
          ? sectors.map(s => <SectorRow key={s.Sector} sector={s} />)
          : <div style={{ color: colors.textSecondary, fontSize: 13, marginTop: 16, textAlign: 'center' }}>No sector data</div>
        }
      </div>
    </div>
  );
};

// needed for the empty chart state icon
function PieChart({ size, color }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>
    </svg>
  );
}
