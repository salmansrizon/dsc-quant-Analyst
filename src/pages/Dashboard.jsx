import { useState, useEffect } from 'react';
import api from '../api/client';

import { 
  BarChart2, 
  Building2, 
  Coins, 
  Clock, 
  TrendingUp, 
  TrendingDown 
} from 'lucide-react';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [gainers, setGainers] = useState([]);
  const [losers, setLosers] = useState([]);
  const [sectors, setSectors] = useState([]);
  const [activeTab, setActiveTab] = useState('gainers');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/api/market-summary'),
      api.get('/api/top-gainers?limit=10'),
      api.get('/api/top-losers?limit=10'),
      api.get('/api/sector-performance'),
    ])
      .then(([s, g, l, sec]) => {
        setSummary(s);
        setGainers(g);
        setLosers(l);
        setSectors(sec);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="page-content">
        <h1 className="page-title">Dashboard</h1>
        <div className="card-grid">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card stat-card">
              <div className="skeleton" style={{ height: 20, width: '60%', marginBottom: 12 }} />
              <div className="skeleton" style={{ height: 36, width: '40%' }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const formatNum = (n) => {
    if (n === null || n === undefined) return '—';
    const num = Number(n);
    if (isNaN(num)) return '—';
    if (num >= 1e9) return (num / 1e9).toFixed(1) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(1) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(1) + 'K';
    return num.toLocaleString();
  };

  const movers = activeTab === 'gainers' ? gainers : losers;

  return (
    <div className="page-content">
      <h1 className="page-title">Market Dashboard</h1>

      {/* Summary Cards */}
      <div className="card-grid" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card stat-card accent">
          <div className="card-header">
            <span className="card-title">Total Stocks</span>
            <div className="stat-icon accent">
              <BarChart2 size={20} />
            </div>
          </div>
          <div className="card-value">{summary?.total_stocks || 0}</div>
          <div className="stat-label">Listed companies</div>
        </div>

        <div className="card stat-card success">
          <div className="card-header">
            <span className="card-title">Sectors</span>
            <div className="stat-icon success">
              <Building2 size={20} />
            </div>
          </div>
          <div className="card-value">{summary?.total_sectors || 0}</div>
          <div className="stat-label">Industry sectors</div>
        </div>

        <div className="card stat-card warning">
          <div className="card-header">
            <span className="card-title">Avg Price</span>
            <div className="stat-icon warning">
              <Coins size={20} />
            </div>
          </div>
          <div className="card-value">৳{summary?.avg_price || 0}</div>
          <div className="stat-label">Average LTP</div>
        </div>

        <div className="card stat-card danger">
          <div className="card-header">
            <span className="card-title">Last Updated</span>
            <div className="stat-icon danger">
              <Clock size={20} />
            </div>
          </div>
          <div className="card-value" style={{ fontSize: 'var(--font-size-lg)' }}>
            {summary?.last_updated ? new Date(summary.last_updated).toLocaleDateString() : '—'}
          </div>
          <div className="stat-label">Data freshness</div>
        </div>
      </div>

      {/* Top Movers */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="tabs">
          <button className={`tab ${activeTab === 'gainers' ? 'active' : ''}`} onClick={() => setActiveTab('gainers')}>
            <TrendingUp size={16} style={{ marginRight: 8, verticalAlign: 'middle' }} /> Top Gainers
          </button>
          <button className={`tab ${activeTab === 'losers' ? 'active' : ''}`} onClick={() => setActiveTab('losers')}>
            <TrendingDown size={16} style={{ marginRight: 8, verticalAlign: 'middle' }} /> Top Losers
          </button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Sector</th>
                <th>LTP</th>
                <th>High</th>
                <th>Low</th>
                <th>YCP</th>
                <th>Change</th>
                <th>Volume</th>
              </tr>
            </thead>
            <tbody>
              {movers.map((s, i) => {
                const ltp = Number(s.LTP) || 0;
                const ycp = Number(s.YCP) || 0;
                const change = ltp - ycp;
                const pct = ycp ? ((change / ycp) * 100).toFixed(2) : 0;
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{s.Symbol}</td>
                    <td style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-family)' }}>{s.Sector}</td>
                    <td>৳{ltp.toFixed(2)}</td>
                    <td>{Number(s.HIGH)?.toFixed(2)}</td>
                    <td>{Number(s.LOW)?.toFixed(2)}</td>
                    <td>{ycp.toFixed(2)}</td>
                    <td className={change >= 0 ? 'positive' : 'negative'}>
                      {change >= 0 ? '+' : ''}{change.toFixed(2)} ({pct}%)
                    </td>
                    <td>{formatNum(s.VOLUME)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sector Performance */}
      <div className="card">
        <div className="card-header">
          <span className="card-title" style={{ fontSize: 'var(--font-size-lg)' }}>Sector Performance</span>
        </div>
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {sectors.map((sec, i) => (
            <div key={i} className="card" style={{ padding: 'var(--space-4)' }}>
              <div style={{ fontWeight: 600, marginBottom: 'var(--space-2)', fontSize: 'var(--font-size-sm)' }}>
                {sec.Sector}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
                <span>{sec.stock_count} stocks</span>
                <span>Avg ৳{sec.avg_ltp}</span>
                <span>Vol {formatNum(sec.total_volume)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
