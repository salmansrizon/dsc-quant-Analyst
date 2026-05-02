import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../api/client';

import { Briefcase, Plus, X, Trash2 } from 'lucide-react';
import SearchDropdown from '../components/SearchDropdown';

export default function Portfolio() {
  const [holdings, setHoldings] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [searchParams] = useSearchParams();

  const [form, setForm] = useState({
    symbol: searchParams.get('add') || '',
    buy_price: searchParams.get('price') || '',
    quantity: '',
    price_target: '',
    stop_loss: '',
    notes: '',
  });

  const fetchPortfolio = () => {
    setLoading(true);
    Promise.all([
      api.get('/api/portfolio'),
      api.get('/api/portfolio/summary'),
    ])
      .then(([h, s]) => { setHoldings(h); setSummary(s); })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchPortfolio();
    if (searchParams.get('add')) setShowAdd(true);
  }, []);

  const addHolding = async (e) => {
    e.preventDefault();
    await api.post('/api/portfolio', {
      symbol: form.symbol.toUpperCase(),
      buy_price: Number(form.buy_price),
      quantity: Number(form.quantity),
      price_target: form.price_target ? Number(form.price_target) : null,
      stop_loss: form.stop_loss ? Number(form.stop_loss) : null,
      notes: form.notes || null,
    });
    setShowAdd(false);
    setForm({ symbol: '', buy_price: '', quantity: '', price_target: '', stop_loss: '', notes: '' });
    fetchPortfolio();
  };

  const deleteHolding = async (id) => {
    await api.delete(`/api/portfolio/${id}`);
    fetchPortfolio();
  };

  const totalInvested = Number(summary?.total_invested) || 0;
  const currentValue = Number(summary?.current_value) || 0;
  const totalPnl = Number(summary?.total_pnl) || 0;
  const pnlPct = totalInvested ? ((totalPnl / totalInvested) * 100).toFixed(2) : 0;

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
        <h1 className="page-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
          <Briefcase className="icon" size={24} color="var(--color-accent)" /> Portfolio
        </h1>
        <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
          <Plus size={18} /> Add Holding
        </button>
      </div>

      {/* Summary Cards */}
      <div className="card-grid" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card stat-card accent">
          <span className="card-title">Total Invested</span>
          <div className="card-value">৳{totalInvested.toLocaleString()}</div>
        </div>
        <div className="card stat-card success">
          <span className="card-title">Current Value</span>
          <div className="card-value">৳{currentValue.toLocaleString()}</div>
        </div>
        <div className={`card stat-card ${totalPnl >= 0 ? 'success' : 'danger'}`}>
          <span className="card-title">Total P&L</span>
          <div className="card-value" style={{ color: totalPnl >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>
            {totalPnl >= 0 ? '+' : ''}৳{totalPnl.toLocaleString()} ({pnlPct}%)
          </div>
        </div>
        <div className="card stat-card warning">
          <span className="card-title">Holdings</span>
          <div className="card-value">{summary?.total_holdings || 0}</div>
        </div>
      </div>

      {/* Add Holding Modal */}
      {showAdd && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowAdd(false)}>
          <div className="modal">
            <div className="modal-header">
              <h3 className="modal-title">Add Holding</h3>
              <button className="modal-close" onClick={() => setShowAdd(false)}>✕</button>
            </div>
            <form onSubmit={addHolding}>
              <div className="form-group">
                <label className="form-label">Symbol</label>
                <SearchDropdown 
                  placeholder="e.g. BRACBANK" 
                  onSelect={(s) => setForm({ ...form, symbol: s })} 
                />
                {form.symbol && <div style={{ fontSize: 'var(--font-size-xs)', marginTop: 4, color: 'var(--color-accent)' }}>Selected: {form.symbol}</div>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Buy Price (৳)</label>
                  <input className="form-input" type="number" step="0.01" placeholder="0.00" value={form.buy_price} onChange={(e) => setForm({ ...form, buy_price: e.target.value })} required />
                </div>
                <div className="form-group">
                  <label className="form-label">Quantity</label>
                  <input className="form-input" type="number" placeholder="0" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Price Target (৳)</label>
                  <input className="form-input" type="number" step="0.01" placeholder="Optional" value={form.price_target} onChange={(e) => setForm({ ...form, price_target: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">Stop Loss (৳)</label>
                  <input className="form-input" type="number" step="0.01" placeholder="Optional" value={form.stop_loss} onChange={(e) => setForm({ ...form, stop_loss: e.target.value })} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <input className="form-input" placeholder="Optional notes..." value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </div>
              <button className="btn btn-primary btn-lg" type="submit" style={{ width: '100%' }}>Add to Portfolio</button>
            </form>
          </div>
        </div>
      )}

      {/* Holdings Table */}
      {holdings.length > 0 ? (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Sector</th>
                <th>Buy Price</th>
                <th>Qty</th>
                <th>Current</th>
                <th>P&L</th>
                <th>P&L %</th>
                <th>Target</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, i) => {
                const pnl = Number(h.pnl) || 0;
                const pnlP = Number(h.pnl_percent) || 0;
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{h.symbol}</td>
                    <td style={{ fontFamily: 'var(--font-family)', color: 'var(--color-text-secondary)' }}>{h.Sector || '—'}</td>
                    <td>৳{Number(h.buy_price).toFixed(2)}</td>
                    <td>{h.quantity}</td>
                    <td>৳{Number(h.current_price)?.toFixed(2) || '—'}</td>
                    <td className={pnl >= 0 ? 'positive' : 'negative'}>
                      {pnl >= 0 ? '+' : ''}৳{pnl.toFixed(2)}
                    </td>
                    <td className={pnlP >= 0 ? 'positive' : 'negative'}>
                      {pnlP >= 0 ? '+' : ''}{pnlP.toFixed(2)}%
                    </td>
                    <td>{h.price_target ? `৳${Number(h.price_target).toFixed(2)}` : '—'}</td>
                    <td>
                      <button className="btn btn-danger btn-sm" onClick={() => deleteHolding(h.id)}>✕</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card empty-state">
          <div className="icon">💼</div>
          <h3>No holdings yet</h3>
          <p>Add your first stock holding to start tracking P&L</p>
        </div>
      )}
    </div>
  );
}
