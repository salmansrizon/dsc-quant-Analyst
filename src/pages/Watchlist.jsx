import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { colors } from '../design';
import { Plus, Trash2, Bell } from 'lucide-react';
import { useToast } from '../components/Toast';
import { SymbolSearch, useMarketPrice } from '../components/SymbolSearch';

const Input = ({ style, ...props }) => (
  <input
    style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13, outline: 'none', ...style }}
    {...props}
  />
);

const Btn = ({ variant = 'primary', style, ...props }) => (
  <button
    style={{
      padding: '6px 14px', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
      background: variant === 'primary' ? colors.accent : variant === 'danger' ? colors.red : colors.surface2,
      color: '#fff',
      ...style,
    }}
    {...props}
  />
);

const AlertInline = ({ symbol, onDone }) => {
  const [target, setTarget] = useState('');
  const [dir, setDir] = useState('above');
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const marketPrice = useMarketPrice(symbol);

  const save = async () => {
    if (!target) return;
    setSaving(true);
    try {
      await apiClient.post('/alerts', { symbol, target_price: parseFloat(target), direction: dir });
      onDone();
      toast.success(`Alert set for ${symbol}`);
    } catch (e) {
      toast.error(e.message || 'Failed to set alert');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <Input placeholder="Target price" value={target} onChange={e => setTarget(e.target.value)} style={{ width: 110 }} />
        <select
          value={dir} onChange={e => setDir(e.target.value)}
          style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 8px', fontSize: 13 }}
        >
          <option value="above">Above</option>
          <option value="below">Below</option>
        </select>
        <Btn onClick={save} disabled={saving} style={{ padding: '6px 10px' }}>{saving ? '…' : 'Set'}</Btn>
        <Btn variant="ghost" onClick={onDone} style={{ padding: '6px 10px' }}>Cancel</Btn>
      </div>
      {marketPrice != null && (
        <button
          type="button"
          onClick={() => setTarget(String(marketPrice))}
          style={{ alignSelf: 'flex-start', background: 'none', border: 'none', cursor: 'pointer', color: colors.accent, fontSize: 11, padding: 0 }}
        >
          Current market price ৳{marketPrice.toFixed(2)} — use as target
        </button>
      )}
    </div>
  );
};

export const WatchlistPage = () => {
  const [items, setItems] = useState([]);
  const [newSymbol, setNewSymbol] = useState('');
  const [adding, setAdding] = useState(false);
  const [alertFor, setAlertFor] = useState(null);
  const navigate = useNavigate();
  const toast = useToast();

  const load = () => apiClient.get('/watchlist').then(d => setItems(Array.isArray(d) ? d : [])).catch(() => {});

  useEffect(() => { load(); }, []);

  const add = async (symbol) => {
    const sym = (symbol ?? newSymbol).trim().toUpperCase();
    if (!sym || adding) return;
    // Optimistically show the row immediately — the BigQuery insert can take
    // several seconds, so waiting on it would make the add feel broken.
    const already = items.some(x => x.symbol === sym);
    if (!already) setItems(prev => [{ symbol: sym, added_at: new Date().toISOString() }, ...prev]);
    setNewSymbol('');
    setAdding(true);
    try {
      await apiClient.post('/watchlist', { symbol: sym });
      toast.success(`${sym} added to watchlist`);
      load();                       // reconcile with server data in the background
    } catch (e) {
      load();                       // resync drops the optimistic row the server rejected
      toast.error(e.message || 'Failed to add symbol');
    } finally {
      setAdding(false);
    }
  };

  const remove = async (symbol) => {
    try { await apiClient.delete(`/watchlist/${symbol}`); load(); } catch (e) { toast.error(e.message || 'Failed to remove symbol'); }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ color: colors.textPrimary, fontSize: 16, fontWeight: 600 }}>Watchlist</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <div style={{ width: 220 }}>
            <SymbolSearch
              value={newSymbol}
              onChange={setNewSymbol}
              onSelect={(row) => add(row.Symbol)}
              onSubmitRaw={(q) => add(q)}
              placeholder="Symbol e.g. ABBANK"
            />
          </div>
          <Btn onClick={() => add()} disabled={adding} style={adding ? { opacity: 0.7, cursor: 'default' } : undefined}>
            {adding ? 'Adding…' : <><Plus size={14} style={{ marginRight: 4, display: 'inline' }} />Add</>}
          </Btn>
        </div>
      </div>

      <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', padding: '8px 16px', borderBottom: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
          <span>Symbol</span>
          <span>Added</span>
          <span>Actions</span>
        </div>
        {items.length === 0 && (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No symbols in watchlist</div>
        )}
        {items.map(item => (
          <div key={item.symbol}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', padding: '10px 16px', borderBottom: `1px solid ${colors.border}`, alignItems: 'center' }}>
              <button
                onClick={() => navigate(`/stocks/${item.symbol}`)}
                style={{ color: colors.accent, fontSize: 14, fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: 0 }}
              >
                {item.symbol}
              </button>
              <span style={{ color: colors.textSecondary, fontSize: 12 }}>{item.added_at ? new Date(item.added_at).toLocaleDateString() : '—'}</span>
              <div style={{ display: 'flex', gap: 6 }}>
                <Btn variant="ghost" onClick={() => setAlertFor(alertFor === item.symbol ? null : item.symbol)} style={{ padding: '6px 10px', minWidth: 36 }} aria-label={`Set price alert for ${item.symbol}`} aria-pressed={alertFor === item.symbol}>
                  <Bell size={14} aria-hidden="true" />
                </Btn>
                <Btn variant="danger" onClick={() => remove(item.symbol)} style={{ padding: '6px 10px', minWidth: 36 }} aria-label={`Remove ${item.symbol} from watchlist`}>
                  <Trash2 size={14} aria-hidden="true" />
                </Btn>
              </div>
            </div>
            {alertFor === item.symbol && (
              <div style={{ padding: '0 16px 12px' }}>
                <AlertInline symbol={item.symbol} onDone={() => setAlertFor(null)} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
