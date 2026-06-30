import React, { useEffect, useRef, useState } from 'react';
import apiClient from '../api/client';
import { colors } from '../design';
import { Plus, ChevronDown, ChevronUp, X } from 'lucide-react';
import { useToast } from '../components/Toast';
import { SymbolSearch, useMarketPrice } from '../components/SymbolSearch';

const PriceSuggestion = ({ price, onApply }) => {
  if (price == null) return null;
  return (
    <button
      type="button"
      onClick={() => onApply(price)}
      style={{ alignSelf: 'flex-start', marginTop: 2, background: 'none', border: 'none', cursor: 'pointer', color: colors.accent, fontSize: 11, padding: 0 }}
    >
      Use market price ৳{price.toFixed(2)}
    </button>
  );
};

const Input = React.forwardRef(({ label, style, ...props }, ref) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    {label && <label style={{ color: colors.textSecondary, fontSize: 12 }}>{label}</label>}
    <input
      ref={ref}
      style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13, ...style }}
      {...props}
    />
  </div>
));

const Btn = ({ variant = 'primary', style, ...props }) => (
  <button style={{
    padding: '7px 16px', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
    background: variant === 'primary' ? colors.accent : variant === 'danger' ? colors.red : colors.surface2,
    color: '#fff', ...style,
  }} {...props} />
);

const AddModal = ({ onClose, onAdd }) => {
  const [form, setForm] = useState({ symbol: '', buy_price: '', quantity: '', notes: '' });
  const [error, setError] = useState('');
  const headingId = 'add-position-title';
  const firstFieldRef = useRef(null);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const toast = useToast();
  const marketPrice = useMarketPrice(form.symbol);

  React.useEffect(() => { firstFieldRef.current?.focus(); }, []);

  const submit = async () => {
    if (!form.symbol || !form.buy_price || !form.quantity) { setError('Symbol, price, and quantity are required.'); return; }
    setError('');
    try {
      await apiClient.post('/portfolio', { symbol: form.symbol.toUpperCase(), buy_price: parseFloat(form.buy_price), quantity: parseInt(form.quantity), notes: form.notes });
      toast.success(`${form.symbol.toUpperCase()} added to portfolio`);
      onAdd();
    } catch (e) { toast.error(e.message || 'Failed to add position'); }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby={headingId}
        style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 6, padding: 24, width: 380 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <span id={headingId} style={{ color: colors.textPrimary, fontSize: 15, fontWeight: 600 }}>Add Position</span>
          <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', color: colors.textSecondary, cursor: 'pointer', padding: 4, borderRadius: 2 }}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ color: colors.textSecondary, fontSize: 12 }}>Symbol</label>
            <SymbolSearch
              inputRef={firstFieldRef}
              value={form.symbol}
              onChange={(v) => setForm(f => ({ ...f, symbol: v }))}
              onSelect={(row) => setForm(f => ({
                ...f,
                symbol: row.Symbol,
                buy_price: f.buy_price || (row.LTP != null ? String(parseFloat(row.LTP)) : f.buy_price),
              }))}
              placeholder="ABBANK"
              showIcon={false}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Input label="Buy Price (৳)" type="number" min="0" step="0.01" value={form.buy_price} onChange={set('buy_price')} />
            <PriceSuggestion price={marketPrice} onApply={(p) => setForm(f => ({ ...f, buy_price: String(p) }))} />
          </div>
          <Input label="Quantity" type="number" min="1" step="1" value={form.quantity} onChange={set('quantity')} />
          <Input label="Notes (optional)" value={form.notes} onChange={set('notes')} />
        </div>
        {error && <div role="alert" style={{ color: colors.red, fontSize: 12, marginTop: 8 }}>{error}</div>}
        <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
          <Btn variant="ghost" onClick={onClose}>Cancel</Btn>
          <Btn onClick={submit}>Add</Btn>
        </div>
      </div>
    </div>
  );
};

const PnlBadge = ({ value }) => {
  const v = parseFloat(value ?? 0);
  return <span style={{ color: v >= 0 ? colors.green : colors.red, fontWeight: 600 }}>{v >= 0 ? '+' : ''}{v.toFixed(2)}</span>;
};

const PortfolioRow = ({ item, onDelete }) => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 80px 80px 80px 80px 80px 40px', padding: '10px 16px', borderBottom: `1px solid ${colors.border}`, alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setOpen(o => !o)}
      >
        <span style={{ color: colors.accent, fontWeight: 600 }}>{item.symbol}</span>
        <span style={{ color: colors.textPrimary, fontSize: 13 }}>৳{parseFloat(item.buy_price).toFixed(2)}</span>
        <span style={{ color: colors.textPrimary, fontSize: 13 }}>{item.quantity}</span>
        <span style={{ color: colors.textPrimary, fontSize: 13 }}>{item.current_price ? `৳${parseFloat(item.current_price).toFixed(2)}` : '—'}</span>
        <PnlBadge value={item.pnl} />
        <span style={{ color: item.pnl_percent >= 0 ? colors.green : colors.red, fontWeight: 600 }}>{item.pnl_percent != null ? `${item.pnl_percent > 0 ? '+' : ''}${parseFloat(item.pnl_percent).toFixed(1)}%` : '—'}</span>
        <span style={{ color: colors.textSecondary }}>{open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</span>
      </div>
      {open && (
        <div style={{ background: colors.surface2, padding: '10px 16px', borderBottom: `1px solid ${colors.border}` }}>
          <div style={{ display: 'flex', gap: 24, color: colors.textSecondary, fontSize: 12, marginBottom: 8 }}>
            {item.buy_date && <span>Bought: {item.buy_date}</span>}
            {item.price_target > 0 && <span>Target: ৳{item.price_target}</span>}
            {item.stop_loss > 0 && <span>Stop-loss: ৳{item.stop_loss}</span>}
            {item.notes && <span>Notes: {item.notes}</span>}
          </div>
          <Btn variant="danger" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => onDelete(item.id)}>Remove</Btn>
        </div>
      )}
    </>
  );
};

export const PortfolioPage = () => {
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const toast = useToast();

  const load = () => {
    apiClient.get('/portfolio').then(d => setItems(Array.isArray(d) ? d : [])).catch(() => {});
    apiClient.get('/portfolio/summary').then(setSummary).catch(() => {});
  };

  useEffect(() => { load(); }, []);

  const del = async (id) => {
    try { await apiClient.delete(`/portfolio/${id}`); load(); } catch (e) { toast.error(e.message || 'Failed to remove position'); }
  };

  return (
    <div>
      {/* Summary bar */}
      {summary && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
          {[
            { label: 'Holdings', value: summary.total_holdings },
            { label: 'Invested', value: summary.total_invested != null ? `৳${parseFloat(summary.total_invested).toLocaleString()}` : '—' },
            { label: 'Current Value', value: summary.current_value != null ? `৳${parseFloat(summary.current_value).toLocaleString()}` : '—' },
            { label: 'Total P&L', value: summary.total_pnl != null ? <span style={{ color: summary.total_pnl >= 0 ? colors.green : colors.red }}>{summary.total_pnl >= 0 ? '+' : ''}৳{parseFloat(summary.total_pnl).toLocaleString()}</span> : '—' },
            { label: 'Avg P&L %', value: summary.avg_pnl_pct != null ? <span style={{ color: summary.avg_pnl_pct >= 0 ? colors.green : colors.red }}>{summary.avg_pnl_pct >= 0 ? '+' : ''}{parseFloat(summary.avg_pnl_pct).toFixed(2)}%</span> : '—' },
          ].map(s => (
            <div key={s.label} style={{ flex: 1, background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '10px 14px' }}>
              <div style={{ color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>{s.label}</div>
              <div style={{ color: colors.textPrimary, fontSize: 18, fontWeight: 600, marginTop: 3 }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ color: colors.textPrimary, fontSize: 16, fontWeight: 600 }}>Positions</span>
        <Btn onClick={() => setShowAdd(true)}><Plus size={14} style={{ marginRight: 4, display: 'inline' }} />Add Position</Btn>
      </div>

      <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 80px 80px 80px 80px 40px', padding: '8px 16px', borderBottom: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
          <span>Symbol</span><span>Buy</span><span>Qty</span><span>LTP</span><span>P&L</span><span>%</span><span></span>
        </div>
        {items.length === 0 && (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No positions yet</div>
        )}
        {items.map(item => <PortfolioRow key={item.id} item={item} onDelete={del} />)}
      </div>

      {showAdd && <AddModal onClose={() => setShowAdd(false)} onAdd={() => { setShowAdd(false); load(); }} />}
    </div>
  );
};
