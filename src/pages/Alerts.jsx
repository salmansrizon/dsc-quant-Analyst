import React, { useEffect, useState } from 'react';
import apiClient from '../api/client';
import { colors } from '../design';
import { Plus, Trash2, CheckCircle, Clock } from 'lucide-react';
import { useToast } from '../components/Toast';

const Input = ({ style, ...props }) => (
  <input style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13, outline: 'none', ...style }} {...props} />
);

const Btn = ({ variant = 'primary', style, ...props }) => (
  <button style={{
    padding: '6px 14px', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
    background: variant === 'primary' ? colors.accent : variant === 'danger' ? colors.red : colors.surface2,
    color: '#fff', ...style,
  }} {...props} />
);

const Tab = ({ active, ...props }) => (
  <button style={{
    padding: '8px 20px', fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none', borderRadius: '3px 3px 0 0',
    background: active ? colors.surface : 'transparent',
    color: active ? colors.textPrimary : colors.textSecondary,
    borderBottom: active ? `2px solid ${colors.accent}` : '2px solid transparent',
  }} {...props} />
);

const AlertRow = ({ alert, onDelete }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 80px 80px 80px auto', padding: '10px 16px', borderBottom: `1px solid ${colors.border}`, alignItems: 'center', gap: 8 }}>
    <span style={{ color: colors.accent, fontWeight: 600 }}>{alert.symbol}</span>
    <div style={{ color: colors.textSecondary, fontSize: 12 }}>
      {alert.current_price != null && <span style={{ color: colors.textPrimary }}>LTP ৳{parseFloat(alert.current_price).toFixed(2)} · </span>}
      Target ৳{parseFloat(alert.target_price).toFixed(2)}
    </div>
    <span style={{ color: alert.direction === 'above' ? colors.green : colors.red, fontSize: 12, fontWeight: 500 }}>
      {alert.direction === 'above' ? '▲ Above' : '▼ Below'}
    </span>
    <span style={{ color: colors.textSecondary, fontSize: 11 }}>{alert.created_at ? new Date(alert.created_at).toLocaleDateString() : '—'}</span>
    <span style={{ color: alert.is_triggered ? colors.green : colors.yellow, fontSize: 12 }}>
      {alert.is_triggered
        ? <><CheckCircle size={12} aria-hidden="true" style={{ display: 'inline', marginRight: 3 }} />Triggered</>
        : <><Clock size={12} aria-hidden="true" style={{ display: 'inline', marginRight: 3 }} />Active</>}
    </span>
    {!alert.is_triggered && (
      <Btn variant="danger" onClick={() => onDelete(alert.id)} style={{ padding: '6px 10px', minWidth: 36 }} aria-label={`Delete alert for ${alert.symbol}`}>
        <Trash2 size={13} aria-hidden="true" />
      </Btn>
    )}
  </div>
);

export const AlertsPage = () => {
  const [alerts, setAlerts] = useState([]);
  const [tab, setTab] = useState('active');
  const [form, setForm] = useState({ symbol: '', target_price: '', direction: 'above' });
  const [adding, setAdding] = useState(false);
  const toast = useToast();

  const load = () => apiClient.get('/alerts').then(d => setAlerts(Array.isArray(d) ? d : [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const del = async (id) => {
    try { await apiClient.delete(`/alerts/${id}`); load(); } catch (e) { toast.error(e.message || 'Failed to delete alert'); }
  };
  const add = async () => {
    if (!form.symbol || !form.target_price) return;
    setAdding(true);
    try {
      await apiClient.post('/alerts', { symbol: form.symbol.toUpperCase(), target_price: parseFloat(form.target_price), direction: form.direction });
      setForm({ symbol: '', target_price: '', direction: 'above' });
      load();
      toast.success('Alert created');
    } catch (e) { toast.error(e.message || 'Failed to create alert'); } finally { setAdding(false); }
  };

  const displayed = tab === 'active' ? alerts.filter(a => !a.is_triggered) : alerts.filter(a => a.is_triggered);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ color: colors.textPrimary, fontSize: 16, fontWeight: 600 }}>Price Alerts</span>
      </div>

      {/* Create form */}
      <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4, padding: 14, marginBottom: 16, display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ color: colors.textSecondary, fontSize: 11 }}>Symbol</label>
          <Input placeholder="ABBANK" value={form.symbol} onChange={e => setForm(f => ({ ...f, symbol: e.target.value }))} style={{ width: 120 }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ color: colors.textSecondary, fontSize: 11 }}>Target Price (৳)</label>
          <Input type="number" placeholder="50.00" value={form.target_price} onChange={e => setForm(f => ({ ...f, target_price: e.target.value }))} style={{ width: 120 }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ color: colors.textSecondary, fontSize: 11 }}>Direction</label>
          <select value={form.direction} onChange={e => setForm(f => ({ ...f, direction: e.target.value }))}
            style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13 }}>
            <option value="above">Above</option>
            <option value="below">Below</option>
          </select>
        </div>
        <Btn onClick={add} disabled={adding}><Plus size={14} style={{ marginRight: 4, display: 'inline' }} />{adding ? 'Adding…' : 'Add Alert'}</Btn>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${colors.border}`, marginBottom: 0 }}>
        <Tab active={tab === 'active'} onClick={() => setTab('active')}>
          Active ({alerts.filter(a => !a.is_triggered).length})
        </Tab>
        <Tab active={tab === 'triggered'} onClick={() => setTab('triggered')}>
          Triggered ({alerts.filter(a => a.is_triggered).length})
        </Tab>
      </div>

      <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderTop: 'none', borderRadius: '0 0 4px 4px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr 80px 80px 80px auto', padding: '8px 16px', borderBottom: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, gap: 8 }}>
          <span>Symbol</span><span>Price</span><span>Direction</span><span>Created</span><span>Status</span><span></span>
        </div>
        {displayed.length === 0 && (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>
            {tab === 'active' ? 'No active alerts' : 'No triggered alerts yet'}
          </div>
        )}
        {displayed.map(a => <AlertRow key={a.id} alert={a} onDelete={del} />)}
      </div>
    </div>
  );
};
