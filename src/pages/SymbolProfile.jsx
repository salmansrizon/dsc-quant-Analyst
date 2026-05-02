import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/client';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { 
  Star, 
  Briefcase, 
  TrendingUp, 
  TrendingDown,
  Info,
  X
} from 'lucide-react';

export default function SymbolProfile() {
  const { symbol } = useParams();
  const [stock, setStock] = useState(null);
  const [history, setHistory] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [watchlistMsg, setWatchlistMsg] = useState('');
  const [showPortfolioModal, setShowPortfolioModal] = useState(false);
  const [portfolioForm, setPortfolioForm] = useState({
    quantity: '',
    price_target: '',
    stop_loss: '',
    notes: ''
  });

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/api/datamatrix?limit=500`),
      api.get(`/api/price-history/${symbol}?limit=90`),
      api.get(`/api/announcements?symbol=${symbol}&limit=20`),
    ])
      .then(([matrix, hist, ann]) => {
        const found = matrix.find((s) => s.Symbol === symbol);
        setStock(found || null);
        const chartData = hist.reverse().map(h => ({
          date: h.Date,
          price: Number(h.CLOSEP_) || Number(h.LTP_) || Number(h.CLOSEP) || Number(h.LTP) || 0
        }));
        setHistory(chartData);
        setAnnouncements(ann);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [symbol]);

  const addToWatchlist = async () => {
    try {
      await api.post('/api/watchlist', { symbol });
      setWatchlistMsg('Added to watchlist ✓');
      setTimeout(() => setWatchlistMsg(''), 2000);
    } catch (err) {
      setWatchlistMsg(err.message);
    }
  };

  const handlePortfolioSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/portfolio', {
        symbol,
        buy_price: Number(stock.LTP),
        quantity: Number(portfolioForm.quantity),
        price_target: portfolioForm.price_target ? Number(portfolioForm.price_target) : null,
        stop_loss: portfolioForm.stop_loss ? Number(portfolioForm.stop_loss) : null,
        notes: portfolioForm.notes || null
      });
      setShowPortfolioModal(false);
      setWatchlistMsg('Added to portfolio ✓');
      setTimeout(() => setWatchlistMsg(''), 2000);
    } catch (err) {
      alert(err.message);
    }
  };

  if (loading) {
    return (
      <div className="page-content">
        <div className="skeleton" style={{ height: 32, width: 200, marginBottom: 24 }} />
        <div className="card-grid">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton card" style={{ height: 80 }} />)}
        </div>
      </div>
    );
  }

  if (!stock) {
    return (
      <div className="page-content">
        <div className="empty-state">
          <div className="icon"><Info size={48} /></div>
          <h3>Symbol not found</h3>
          <p>{symbol} not found in datamatrix</p>
          <Link to="/symbols" className="btn btn-primary" style={{ marginTop: 16 }}>Browse Symbols</Link>
        </div>
      </div>
    );
  }

  const ltp = Number(stock.LTP) || 0;
  const ycp = Number(stock.YCP) || 0;
  const change = ltp - ycp;
  const pct = ycp ? ((change / ycp) * 100).toFixed(2) : 0;
  
  const high = Number(stock.High) || Number(stock.HIGH) || 0;
  const low = Number(stock.Low) || Number(stock.LOW) || 0;
  const volume = Number(stock.Volume_Qty_) || Number(stock['Volume(Qty)']) || Number(stock.VOLUME) || 0;

  return (
    <div className="page-content">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-6)' }}>
        <div>
          <h1 className="page-title" style={{ marginBottom: 4 }}>{symbol}</h1>
          <span className="badge badge-accent">{stock.Sector}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {watchlistMsg && <span className="badge badge-success">{watchlistMsg}</span>}
          <button className="btn btn-secondary" onClick={addToWatchlist} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Star size={16} /> Watchlist
          </button>
          <button className="btn btn-primary" onClick={() => setShowPortfolioModal(true)} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Briefcase size={16} /> Add to Portfolio
          </button>
        </div>
      </div>

      {showPortfolioModal && (
        <div className="modal-overlay">
          <div className="modal-content card" style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <h3>Add {symbol} to Portfolio</h3>
              <button className="btn-close" onClick={() => setShowPortfolioModal(false)}><X size={20} /></button>
            </div>
            <form onSubmit={handlePortfolioSubmit}>
              <div className="form-group">
                <label className="form-label">Price (LTP preloaded)</label>
                <input className="form-input" value={ltp} disabled />
              </div>
              <div className="form-group">
                <label className="form-label">Quantity</label>
                <input 
                  className="form-input" 
                  type="number" 
                  required 
                  value={portfolioForm.quantity} 
                  onChange={e => setPortfolioForm({...portfolioForm, quantity: e.target.value})}
                  placeholder="Number of shares"
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Target Price</label>
                  <input 
                    className="form-input" 
                    type="number" 
                    value={portfolioForm.price_target} 
                    onChange={e => setPortfolioForm({...portfolioForm, price_target: e.target.value})}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Stop Loss</label>
                  <input 
                    className="form-input" 
                    type="number" 
                    value={portfolioForm.stop_loss} 
                    onChange={e => setPortfolioForm({...portfolioForm, stop_loss: e.target.value})}
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-ghost" onClick={() => setShowPortfolioModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Holding</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Price Overview */}
      <div className="card-grid" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card stat-card accent">
          <span className="card-title">LTP</span>
          <div className="card-value">৳{ltp.toFixed(2)}</div>
          <span className={`badge ${change >= 0 ? 'badge-success' : 'badge-danger'}`}>
            {change >= 0 ? '▲' : '▼'} {Math.abs(change).toFixed(2)} ({pct}%)
          </span>
        </div>
        <div className="card">
          <span className="card-title">High</span>
          <div className="card-value" style={{ fontSize: 'var(--font-size-2xl)' }}>৳{high.toFixed(2)}</div>
        </div>
        <div className="card">
          <span className="card-title">Low</span>
          <div className="card-value" style={{ fontSize: 'var(--font-size-2xl)' }}>৳{low.toFixed(2)}</div>
        </div>
        <div className="card">
          <span className="card-title">Volume</span>
          <div className="card-value" style={{ fontSize: 'var(--font-size-2xl)' }}>{volume.toLocaleString()}</div>
        </div>
      </div>

      {/* Professional Price Chart */}
      <div className="card" style={{ marginBottom: 'var(--space-6)', height: 400 }}>
        <div className="card-header">
          <span className="card-title" style={{ fontSize: 'var(--font-size-lg)' }}>Price Performance (90 days)</span>
        </div>
        <div style={{ width: '100%', height: 320 }}>
          {history.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-accent)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" vertical={false} />
                <XAxis 
                  dataKey="date" 
                  hide={true} 
                />
                <YAxis 
                  domain={['auto', 'auto']} 
                  orientation="right"
                  tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip 
                  contentStyle={{ 
                    background: 'var(--color-bg-card)', 
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 'var(--font-size-sm)'
                  }}
                  itemStyle={{ color: 'var(--color-text-primary)' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="price" 
                  stroke="var(--color-accent)" 
                  strokeWidth={2}
                  fillOpacity={1} 
                  fill="url(#colorPrice)" 
                  animationDuration={1500}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No price history available</p></div>
          )}
        </div>
      </div>

      {/* Announcements */}
      <div className="card">
        <div className="card-header">
          <span className="card-title" style={{ fontSize: 'var(--font-size-lg)' }}>Recent Announcements</span>
          <span className="badge badge-accent">{announcements.length}</span>
        </div>
        {announcements.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {announcements.map((a, i) => (
              <div key={i} style={{ padding: '12px', background: 'var(--color-bg-secondary)', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--color-accent)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 'var(--font-size-sm)', fontWeight: 600 }}>{a.Announcement_Type || 'Announcement'}</span>
                  <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>{a.Date}</span>
                </div>
                <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                  {a.Details?.substring(0, 200)}{a.Details?.length > 200 ? '...' : ''}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state"><p>No announcements</p></div>
        )}
      </div>
    </div>
  );
}
