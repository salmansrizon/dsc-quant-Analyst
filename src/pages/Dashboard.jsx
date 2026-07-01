import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer, PieChart as RechartsPieChart, Pie } from 'recharts';
import { TrendingUp, TrendingDown, Clock } from 'lucide-react';
import apiClient from '../api/client';
import { colors } from '../design';

const SymbolButton = ({ symbol, style }) => {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(`/stocks/${symbol}`)}
      style={{ color: colors.textPrimary, fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', padding: 0, textAlign: 'left', ...style }}
    >
      {symbol}
    </button>
  );
};

const LEADERBOARD_TABS = [
  { key: 'value', label: 'Top Value' },
  { key: 'gainer', label: 'Top Gainer' },
  { key: 'loser', label: 'Top Loser' },
  { key: 'volume', label: 'Top Volume' },
  { key: 'trade', label: 'Top Trade' },
];

const Tab = ({ active, ...props }) => (
  <button style={{
    padding: '8px 16px', fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none', borderRadius: '3px 3px 0 0',
    background: active ? colors.surface : 'transparent',
    color: active ? colors.textPrimary : colors.textSecondary,
    borderBottom: active ? `2px solid ${colors.accent}` : '2px solid transparent',
  }} {...props} />
);

const LeaderboardRow = ({ row }) => {
  const changePct = row.ChangePct != null ? parseFloat(row.ChangePct) : null;
  const positive = changePct != null && changePct >= 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: `1px solid ${colors.border}`, fontSize: 13 }}>
      <SymbolButton symbol={row.Symbol} style={{ fontSize: 13, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} />
      <span style={{ color: colors.textSecondary, fontSize: 12, flexShrink: 0 }}>{row.Sector}</span>
      <span style={{ color: colors.textPrimary, fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
        {row.LTP != null ? `৳${parseFloat(row.LTP).toFixed(2)}` : '—'}
      </span>
      {changePct != null && (
        <span className={`ds-badge ${positive ? 'ds-badge-green' : 'ds-badge-red'}`}>
          {positive ? '+' : ''}{changePct.toFixed(2)}%
        </span>
      )}
    </div>
  );
};

const LeaderboardWidget = () => {
  const [tab, setTab] = useState('value');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get(`/market/leaderboard?metric=${tab}&limit=10`)
      .then(d => setRows(Array.isArray(d) ? d : []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [tab]);

  return (
    <div className="ds-card" style={{ padding: 20, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: `1px solid ${colors.border}`, marginBottom: 4 }}>
        {LEADERBOARD_TABS.map(t => (
          <Tab key={t.key} active={tab === t.key} onClick={() => setTab(t.key)}>{t.label}</Tab>
        ))}
      </div>
      <div data-testid="leaderboard-list">
        {loading ? (
          <div className="skeleton" style={{ height: 160, marginTop: 12 }} />
        ) : rows.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No data</div>
        ) : (
          rows.map(r => <LeaderboardRow key={r.Symbol} row={r} />)
        )}
      </div>
    </div>
  );
};

const EXTREMES_TABS = [
  { key: 'pe_low', label: 'Lowest PE' },
  { key: 'pe_high', label: 'Highest PE' },
  { key: 'director_holding_low', label: 'Lowest Director Hold.' },
  { key: 'director_holding_high', label: 'Highest Director Hold.' },
  { key: 'nav_price_low', label: 'Lowest NAV/Price' },
  { key: 'nav_price_high', label: 'Highest NAV/Price' },
];

const ExtremesRow = ({ row }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: `1px solid ${colors.border}`, fontSize: 13 }}>
    <SymbolButton symbol={row.Symbol} style={{ fontSize: 13, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} />
    <span style={{ color: colors.textSecondary, fontSize: 12, flexShrink: 0 }}>{row.Sector}</span>
    <span style={{ color: colors.textPrimary, fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
      {row.LTP != null ? `৳${parseFloat(row.LTP).toFixed(2)}` : '—'}
    </span>
    <span style={{ color: colors.textPrimary, fontVariantNumeric: 'tabular-nums', flexShrink: 0, fontWeight: 600 }}>
      {row.MetricValue != null ? parseFloat(row.MetricValue).toFixed(2) : '—'}
    </span>
  </div>
);

const FundamentalExtremesWidget = () => {
  const [tab, setTab] = useState('pe_low');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get(`/market/extremes?metric=${tab}&limit=10`)
      .then(d => setRows(Array.isArray(d) ? d : []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [tab]);

  return (
    <div className="ds-card" style={{ padding: 20, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, borderBottom: `1px solid ${colors.border}`, marginBottom: 4 }}>
        {EXTREMES_TABS.map(t => (
          <Tab key={t.key} active={tab === t.key} onClick={() => setTab(t.key)}>{t.label}</Tab>
        ))}
      </div>
      <div data-testid="extremes-list">
        {loading ? (
          <div className="skeleton" style={{ height: 160, marginTop: 12 }} />
        ) : rows.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No data</div>
        ) : (
          rows.map(r => <ExtremesRow key={r.Symbol} row={r} />)
        )}
      </div>
    </div>
  );
};

const TECHNICAL_EXTREMES_TABS = [
  { key: 'rsi_low', label: 'Lowest RSI' },
  { key: 'rsi_high', label: 'Highest RSI' },
  { key: 'macd_low', label: 'Lowest MACD' },
  { key: 'macd_high', label: 'Highest MACD' },
  { key: 'stochastic_low', label: 'Lowest Stochastic' },
  { key: 'stochastic_high', label: 'Highest Stochastic' },
];

const TechnicalExtremesWidget = () => {
  const [tab, setTab] = useState('rsi_low');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiClient.get(`/market/technical-extremes?metric=${tab}&limit=10`)
      .then(d => setRows(Array.isArray(d) ? d : []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [tab]);

  return (
    <div className="ds-card" style={{ padding: 20, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, borderBottom: `1px solid ${colors.border}`, marginBottom: 4 }}>
        {TECHNICAL_EXTREMES_TABS.map(t => (
          <Tab key={t.key} active={tab === t.key} onClick={() => setTab(t.key)}>{t.label}</Tab>
        ))}
      </div>
      <div data-testid="technical-extremes-list">
        {loading ? (
          <div className="skeleton" style={{ height: 160, marginTop: 12 }} />
        ) : rows.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No data</div>
        ) : (
          rows.map(r => <ExtremesRow key={r.Symbol} row={r} />)
        )}
      </div>
    </div>
  );
};

const SENTIMENT_BADGE_CLASS = {
  Positive: 'ds-badge-green',
  Negative: 'ds-badge-red',
};

const AnnouncementRow = ({ row }) => (
  <div style={{ padding: '10px 0', borderBottom: `1px solid ${colors.border}` }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
      <SymbolButton symbol={row.Symbol} style={{ fontSize: 13 }} />
      <span style={{ color: colors.textSecondary, fontSize: 11 }}>{row.Announcement_Type}</span>
      {row.Sentiment && (
        <span className={`ds-badge ${SENTIMENT_BADGE_CLASS[row.Sentiment] || ''}`}>{row.Sentiment}</span>
      )}
      <span style={{ color: colors.textSecondary, fontSize: 11, marginLeft: 'auto' }}>{row.Date}</span>
    </div>
    <div style={{ color: colors.textSecondary, fontSize: 13 }}>{row.Details}</div>
  </div>
);

const AnnouncementsWidget = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/market/announcements?limit=20')
      .then(d => setRows(Array.isArray(d) ? d : []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="ds-card" style={{ padding: 20, display: 'flex', flexDirection: 'column' }}>
      <div style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 600, marginBottom: 8 }}>News & Announcements</div>
      <div data-testid="announcements-feed" style={{ maxHeight: 360, overflowY: 'auto' }}>
        {loading ? (
          <div className="skeleton" style={{ height: 160 }} />
        ) : rows.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No announcements</div>
        ) : (
          rows.map((r, i) => <AnnouncementRow key={`${r.Symbol}-${r.Date}-${i}`} row={r} />)
        )}
      </div>
    </div>
  );
};

const SECTOR_TABS = [
  { key: 'pe', label: 'Sector PE' },
  { key: 'trade_value', label: 'Trade Value' },
  { key: 'gainer_loser', label: 'Gainer / Loser' },
];

const SectorTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: colors.surface2, border: `1px solid ${colors.border}`,
      borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: 'var(--shadow-md)',
    }}>
      <div style={{ color: colors.textSecondary, marginBottom: 4 }}>{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.fill, fontWeight: 600 }}>
          {p.name}: {Number(p.value).toLocaleString()}
        </div>
      ))}
    </div>
  );
};

const SectorInsightsWidget = () => {
  const [tab, setTab] = useState('pe');
  const [sectors, setSectors] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/market/sectors/breakdown')
      .then(d => setSectors(Array.isArray(d) ? d : []))
      .catch(() => setSectors([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="ds-card" style={{ padding: 20, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', gap: 4, borderBottom: `1px solid ${colors.border}`, marginBottom: 4 }}>
        {SECTOR_TABS.map(t => (
          <Tab key={t.key} active={tab === t.key} onClick={() => setTab(t.key)}>{t.label}</Tab>
        ))}
      </div>
      <div data-testid="sector-insights-chart" style={{ height: 220, marginTop: 8 }}>
        {loading ? (
          <div className="skeleton" style={{ height: '100%' }} />
        ) : sectors.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No data</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sectors} barCategoryGap="28%">
              <XAxis dataKey="Sector" tick={{ fill: 'var(--color-text-secondary)', fontSize: 10 }} axisLine={false} tickLine={false} interval={0} angle={-35} textAnchor="end" height={56} />
              <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} width={44} />
              <Tooltip content={<SectorTooltip />} cursor={{ fill: 'var(--color-accent-subtle)' }} />
              {tab === 'pe' && <Bar dataKey="AvgPE" name="Avg PE" radius={[5, 5, 0, 0]} fill="var(--color-accent)" />}
              {tab === 'trade_value' && <Bar dataKey="TotalTradeValue" name="Trade Value" radius={[5, 5, 0, 0]} fill="var(--color-accent)" />}
              {tab === 'gainer_loser' && (
                <>
                  <Bar dataKey="GainersCount" name="Gainers" stackId="gl" fill="var(--color-green)" />
                  <Bar dataKey="LosersCount" name="Losers" stackId="gl" radius={[5, 5, 0, 0]} fill="var(--color-red)" />
                </>
              )}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

const StrengthMeter = ({ gainers, losers, unchanged }) => {
  const total = gainers + losers + unchanged || 1;
  const gPct = (gainers / total) * 100;
  const lPct = (losers / total) * 100;
  const uPct = (unchanged / total) * 100;
  return (
    <div data-testid="strength-meter">
      <div style={{ display: 'flex', height: 14, borderRadius: 7, overflow: 'hidden' }}>
        <div style={{ width: `${gPct}%`, background: 'var(--color-green)' }} />
        <div style={{ width: `${uPct}%`, background: 'var(--color-yellow)' }} />
        <div style={{ width: `${lPct}%`, background: 'var(--color-red)' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontSize: 12 }}>
        <span style={{ color: 'var(--color-green)' }}>{gainers} Gainers</span>
        <span style={{ color: colors.textSecondary }}>{unchanged} Unchanged</span>
        <span style={{ color: 'var(--color-red)' }}>{losers} Losers</span>
      </div>
    </div>
  );
};

const STRENGTH_PIE_DATA = (gainers, losers, unchanged) => ([
  { name: 'Gainers', value: gainers, fill: 'var(--color-green)' },
  { name: 'Losers', value: losers, fill: 'var(--color-red)' },
  { name: 'Unchanged', value: unchanged, fill: 'var(--color-yellow)' },
]);

const StrengthPie = ({ gainers, losers, unchanged }) => {
  const data = STRENGTH_PIE_DATA(gainers, losers, unchanged);
  return (
    <div data-testid="strength-pie" style={{ height: 180 }}>
      <ResponsiveContainer width="100%" height="100%">
        <RechartsPieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={40} outerRadius={70} paddingAngle={2}>
            {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
          </Pie>
          <Tooltip />
        </RechartsPieChart>
      </ResponsiveContainer>
    </div>
  );
};

const MarketStrengthWidget = () => {
  const [view, setView] = useState('meter');
  const [composition, setComposition] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/market/strength')
      .then(d => setComposition(d))
      .catch(() => setComposition(null))
      .finally(() => setLoading(false));
  }, []);

  const gainers = composition?.Gainers ?? 0;
  const losers = composition?.Losers ?? 0;
  const unchanged = composition?.Unchanged ?? 0;

  return (
    <div className="ds-card" data-testid="market-strength-widget" style={{ padding: 20, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 600 }}>Market Strength</div>
        <div style={{ display: 'flex', gap: 4 }}>
          <Tab active={view === 'meter'} onClick={() => setView('meter')}>Meter</Tab>
          <Tab active={view === 'pie'} onClick={() => setView('pie')}>Pie</Tab>
        </div>
      </div>
      {loading ? (
        <div className="skeleton" style={{ height: 60 }} />
      ) : view === 'meter' ? (
        <StrengthMeter gainers={gainers} losers={losers} unchanged={unchanged} />
      ) : (
        <StrengthPie gainers={gainers} losers={losers} unchanged={unchanged} />
      )}
    </div>
  );
};

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
          />
        </div>

        {summary?.last_updated && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: colors.textSecondary, fontSize: 12 }}>
            <Clock size={12} aria-hidden="true" />
            Market data last refreshed {summary.last_updated}
          </div>
        )}

        {/* Market strength */}
        <MarketStrengthWidget />

        {/* Leaderboard */}
        <LeaderboardWidget />

        {/* Sector insights */}
        <SectorInsightsWidget />

        {/* Fundamental extremes */}
        <FundamentalExtremesWidget />

        {/* Technical extremes */}
        <TechnicalExtremesWidget />

        {/* News & announcements */}
        <AnnouncementsWidget />

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
