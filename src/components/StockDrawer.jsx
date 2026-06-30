import React, { useEffect, useState } from 'react';
import { X, Bell, TrendingUp, TrendingDown } from 'lucide-react';
import { colors } from '../design';
import apiClient from '../api/client';

const Btn = ({ variant = 'primary', style, ...props }) => (
  <button style={{
    padding: '6px 14px', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
    background: variant === 'primary' ? colors.accent : variant === 'ghost' ? colors.surface2 : colors.red,
    color: '#fff', ...style,
  }} {...props} />
);

const Input = ({ style, ...props }) => (
  <input style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13, outline: 'none', ...style }} {...props} />
);

export const StockDrawer = ({ symbol, onClose }) => {
  const [data, setData] = useState(null);
  const [alertTarget, setAlertTarget] = useState('');
  const [alertDir, setAlertDir] = useState('above');
  const [alertSaving, setAlertSaving] = useState(false);
  const [alertDone, setAlertDone] = useState(false);

  useEffect(() => {
    apiClient.get(`/market/stock/${symbol}`).then(setData).catch(() => setData({ symbol, error: true }));
  }, [symbol]);

  const setAlert = async () => {
    if (!alertTarget) return;
    setAlertSaving(true);
    try {
      await apiClient.post('/alerts', { symbol, target_price: parseFloat(alertTarget), direction: alertDir });
      setAlertDone(true);
    } catch (e) { alert(e.message); } finally { setAlertSaving(false); }
  };

  const ltp = data?.LTP != null ? parseFloat(data.LTP) : null;
  const change = data?.Change != null ? parseFloat(data.Change) : null;
  const changePct = data?.ChangePct != null ? parseFloat(data.ChangePct) : null;
  const isUp = change != null && change >= 0;

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 150 }} />
      <div style={{
        position: 'fixed', right: 0, top: 0, bottom: 0, width: 380,
        background: colors.surface, borderLeft: `1px solid ${colors.border}`,
        zIndex: 151, display: 'flex', flexDirection: 'column', overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: `1px solid ${colors.border}` }}>
          <div>
            <div style={{ color: colors.textPrimary, fontSize: 18, fontWeight: 700 }}>{symbol}</div>
            {data && !data.error && <div style={{ color: colors.textSecondary, fontSize: 12 }}>{data.Company ?? data.FullName ?? ''}</div>}
          </div>
          <button aria-label="Close" onClick={onClose} style={{ background: 'none', border: 'none', color: colors.textSecondary, cursor: 'pointer' }}><X size={20} /></button>
        </div>

        {/* Price */}
        {data && !data.error && (
          <div style={{ padding: '20px 20px 0' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
              <span style={{ color: colors.textPrimary, fontSize: 32, fontWeight: 700 }}>
                {ltp != null ? `৳${ltp.toFixed(2)}` : '—'}
              </span>
              {change != null && (
                <span style={{ color: isUp ? colors.green : colors.red, fontSize: 15, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                  {isUp ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                  {isUp ? '+' : ''}{change.toFixed(2)} ({changePct != null ? `${isUp ? '+' : ''}${changePct.toFixed(2)}%` : ''})
                </span>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 16 }}>
              {[
                ['Open', data.Open], ['High', data.High], ['Low', data.Low], ['Volume', data.Volume],
                ['Turnover', data.Turnover], ['52W High', data['52WHigh']], ['52W Low', data['52WLow']], ['P/E', data.PE],
              ].filter(([, v]) => v != null).map(([label, value]) => (
                <div key={label} style={{ background: colors.surface2, borderRadius: 3, padding: '8px 10px' }}>
                  <div style={{ color: colors.textSecondary, fontSize: 11 }}>{label}</div>
                  <div style={{ color: colors.textPrimary, fontSize: 13, fontWeight: 500, marginTop: 2 }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {data?.error && (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No data for {symbol}</div>
        )}

        {!data && (
          <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>Loading…</div>
        )}

        {/* Set Alert */}
        <div style={{ padding: 20, marginTop: 'auto', borderTop: `1px solid ${colors.border}` }}>
          <div style={{ color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Bell size={12} /> Set Price Alert
          </div>
          {alertDone ? (
            <div style={{ color: colors.green, fontSize: 13 }}>Alert set successfully!</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                <Input placeholder="Target" value={alertTarget} onChange={e => setAlertTarget(e.target.value)} style={{ width: 100 }} />
                <select value={alertDir} onChange={e => setAlertDir(e.target.value)}
                  style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 8px', fontSize: 13 }}>
                  <option value="above">Above</option>
                  <option value="below">Below</option>
                </select>
                <Btn onClick={setAlert} disabled={alertSaving || !alertTarget}>{alertSaving ? '…' : 'Set'}</Btn>
              </div>
              {ltp != null && (
                <button
                  type="button"
                  onClick={() => setAlertTarget(ltp.toFixed(2))}
                  style={{ alignSelf: 'flex-start', background: 'none', border: 'none', cursor: 'pointer', color: colors.accent, fontSize: 11, padding: 0 }}
                >
                  Current market price ৳{ltp.toFixed(2)} — use as target
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
};
