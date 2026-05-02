import { useState, useEffect } from 'react';
import api from '../api/client';

import { Bell, Plus, X, Trash2, ArrowUp, ArrowDown } from 'lucide-react';
import SearchDropdown from '../components/SearchDropdown';

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ symbol: '', target_price: '', direction: 'above' });

  const fetchAlerts = () => {
    setLoading(true);
    api.get('/api/alerts')
      .then(setAlerts)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchAlerts(); }, []);

  const createAlert = async (e) => {
    e.preventDefault();
    await api.post('/api/alerts', {
      symbol: form.symbol.toUpperCase(),
      target_price: Number(form.target_price),
      direction: form.direction,
    });
    setShowAdd(false);
    setForm({ symbol: '', target_price: '', direction: 'above' });
    fetchAlerts();
  };

  const deleteAlert = async (id) => {
    await api.delete(`/api/alerts/${id}`);
    fetchAlerts();
  };

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
        <h1 className="page-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
          <Bell className="icon" size={24} color="var(--color-accent)" /> Price Alerts
        </h1>
        <button className="btn btn-primary" onClick={() => setShowAdd(!showAdd)}>
          <Plus size={18} /> New Alert
        </button>
      </div>

      {showAdd && (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowAdd(false)}>
          <div className="modal">
            <div className="modal-header">
              <h3 className="modal-title">Create Price Alert</h3>
              <button className="modal-close" onClick={() => setShowAdd(false)}>✕</button>
            </div>
            <form onSubmit={createAlert}>
              <div className="form-group">
                <label className="form-label">Symbol</label>
                <SearchDropdown 
                  placeholder="e.g. BRACBANK" 
                  onSelect={(s) => setForm({ ...form, symbol: s })} 
                />
                {form.symbol && <div style={{ fontSize: 'var(--font-size-xs)', marginTop: 4, color: 'var(--color-accent)' }}>Selected: {form.symbol}</div>}
              </div>
              <div className="form-group">
                <label className="form-label">Target Price (৳)</label>
                <input className="form-input" type="number" step="0.01" placeholder="0.00" value={form.target_price} onChange={(e) => setForm({ ...form, target_price: e.target.value })} required />
              </div>
              <div className="form-group">
                <label className="form-label">Direction</label>
                <select className="form-input" value={form.direction} onChange={(e) => setForm({ ...form, direction: e.target.value })}>
                  <option value="above">Price goes ABOVE target</option>
                  <option value="below">Price goes BELOW target</option>
                </select>
              </div>
              <button className="btn btn-primary btn-lg" type="submit" style={{ width: '100%' }}>Create Alert</button>
            </form>
          </div>
        </div>
      )}

      {alerts.length > 0 ? (
        <div className="card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Target</th>
                <th>Direction</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{a.symbol}</td>
                  <td>৳{Number(a.target_price).toFixed(2)}</td>
                  <td>
                    <span className={`badge ${a.direction === 'above' ? 'badge-success' : 'badge-danger'}`}>
                      {a.direction === 'above' ? <><ArrowUp size={12} style={{ marginRight: 4 }} /> Above</> : <><ArrowDown size={12} style={{ marginRight: 4 }} /> Below</>}
                    </span>
                  </td>
                  <td>
                    {a.is_triggered
                      ? <span className="badge badge-warning">Triggered</span>
                      : <span className="badge badge-accent">Active</span>
                    }
                  </td>
                  <td style={{ color: 'var(--color-text-muted)' }}>{a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}</td>
                  <td>
                    <button className="btn btn-danger btn-sm" onClick={() => deleteAlert(a.id)}>
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card empty-state">
          <div className="icon">🔔</div>
          <h3>No price alerts</h3>
          <p>Create alerts to get notified when stocks hit your target price</p>
        </div>
      )}
    </div>
  );
}
