import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/client';

import { Star, Trash2, X } from 'lucide-react';

export default function Watchlist() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchWatchlist = () => {
    setLoading(true);
    api.get('/api/watchlist')
      .then(setItems)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchWatchlist(); }, []);

  const remove = async (symbol) => {
    await api.delete(`/api/watchlist/${symbol}`);
    fetchWatchlist();
  };

  if (loading) {
    return (
      <div className="page-content">
        <h1 className="page-title">Watchlist</h1>
        {[1, 2, 3].map((i) => <div key={i} className="skeleton card" style={{ height: 60, marginBottom: 8 }} />)}
      </div>
    );
  }

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
        <h1 className="page-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
          <Star className="icon" size={24} color="var(--color-accent)" fill="var(--color-accent)" /> Watchlist
        </h1>
        <span className="badge badge-accent">{items.length} symbols</span>
      </div>

      {items.length === 0 ? (
        <div className="card empty-state">
          <div className="icon"><Star size={48} /></div>
          <h3>No symbols in watchlist</h3>
          <p>Browse symbols and add them to your watchlist</p>
          <Link to="/symbols" className="btn btn-primary" style={{ marginTop: 16 }}>Browse Symbols</Link>
        </div>
      ) : (
        <div className="card">
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
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => {
                const ltp = Number(item.LTP) || 0;
                const ycp = Number(item.YCP) || 0;
                const change = ltp - ycp;
                const pct = ycp ? ((change / ycp) * 100).toFixed(2) : 0;
                return (
                  <tr key={i}>
                    <td><Link to={`/symbol/${item.symbol}`} style={{ fontWeight: 600 }}>{item.symbol}</Link></td>
                    <td style={{ fontFamily: 'var(--font-family)', color: 'var(--color-text-secondary)' }}>{item.Sector || '—'}</td>
                    <td>৳{ltp.toFixed(2)}</td>
                    <td>{Number(item.HIGH)?.toFixed(2) || '—'}</td>
                    <td>{Number(item.LOW)?.toFixed(2) || '—'}</td>
                    <td>{ycp.toFixed(2)}</td>
                    <td className={change >= 0 ? 'positive' : 'negative'}>
                      {change >= 0 ? '+' : ''}{change.toFixed(2)} ({pct}%)
                    </td>
                    <td>{Number(item.VOLUME)?.toLocaleString() || '—'}</td>
                    <td>
                      <button className="btn btn-danger btn-sm" onClick={() => remove(item.symbol)}>
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
