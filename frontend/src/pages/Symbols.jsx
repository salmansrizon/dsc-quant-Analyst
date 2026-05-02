import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import { TrendingUp } from 'lucide-react';
import SearchDropdown from '../components/SearchDropdown';

export default function Symbols() {
  const [stocks, setStocks] = useState([]);
  const [sectors, setSectors] = useState([]);
  const [selectedSector, setSelectedSector] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/api/sectors').then(setSectors).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    const url = selectedSector
      ? `/api/datamatrix?sector=${encodeURIComponent(selectedSector)}&limit=500`
      : '/api/datamatrix?limit=500';
    api.get(url)
      .then(setStocks)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [selectedSector]);

  const filtered = stocks.filter((s) =>
    s.Symbol?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
        <h1 className="page-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
          <TrendingUp size={24} color="var(--color-accent)" /> All Symbols
        </h1>
        <div style={{ width: 280 }}>
          <SearchDropdown placeholder="Jump to symbol..." />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 'var(--space-5)', flexWrap: 'wrap' }}>
        <input
          className="form-input"
          placeholder="Search symbol..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 240 }}
        />
        <select
          className="form-input"
          value={selectedSector}
          onChange={(e) => setSelectedSector(e.target.value)}
          style={{ width: 240 }}
        >
          <option value="">All Sectors</option>
          {sectors.map((s, i) => (
            <option key={i} value={s.Sector}>{s.Sector}</option>
          ))}
        </select>
        <span className="badge badge-accent" style={{ alignSelf: 'center' }}>{filtered.length} stocks</span>
      </div>

      {loading ? (
        <div className="card">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton" style={{ height: 40, marginBottom: 4 }} />
          ))}
        </div>
      ) : (
        <div className="card">
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Sector</th>
                  <th>LTP</th>
                  <th>High</th>
                  <th>Low</th>
                  <th>Close</th>
                  <th>YCP</th>
                  <th>Change</th>
                  <th>Volume</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) => {
                  const ltp = Number(s.LTP) || 0;
                  const ycp = Number(s.YCP) || 0;
                  const change = ltp - ycp;
                  const pct = ycp ? ((change / ycp) * 100).toFixed(2) : 0;
                  return (
                    <tr key={i}>
                      <td><Link to={`/symbol/${s.Symbol}`} style={{ fontWeight: 600 }}>{s.Symbol}</Link></td>
                      <td style={{ fontFamily: 'var(--font-family)', color: 'var(--color-text-secondary)' }}>{s.Sector}</td>
                      <td>৳{ltp.toFixed(2)}</td>
                      <td>{Number(s.HIGH)?.toFixed(2)}</td>
                      <td>{Number(s.LOW)?.toFixed(2)}</td>
                      <td>{Number(s.CLOSEP)?.toFixed(2)}</td>
                      <td>{ycp.toFixed(2)}</td>
                      <td className={change >= 0 ? 'positive' : 'negative'}>
                        {change >= 0 ? '+' : ''}{change.toFixed(2)} ({pct}%)
                      </td>
                      <td>{Number(s.VOLUME)?.toLocaleString()}</td>
                      <td>{Number(s.VALUE)?.toLocaleString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
