import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { TrendingUp, TrendingDown, Bell } from 'lucide-react';
import { colors, card } from '../design';
import apiClient from '../api/client';
import { CandlestickChart, VolumeChart } from '../components/CandlestickChart';

const Btn = (props) => (
  <button style={{
    padding: '6px 14px', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
    background: colors.accent, color: '#fff',
  }} {...props} />
);

const Input = (props) => (
  <input style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13, outline: 'none', width: 100 }} {...props} />
);

export const StockProfilePage = () => {
  const { symbol } = useParams();
  const [data, setData] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [history, setHistory] = useState([]);
  const [alertTarget, setAlertTarget] = useState('');
  const [alertDir, setAlertDir] = useState('above');
  const [alertSaving, setAlertSaving] = useState(false);
  const [alertDone, setAlertDone] = useState(false);
  const [alertError, setAlertError] = useState('');

  useEffect(() => {
    setData(null);
    setNotFound(false);
    setHistory([]);
    apiClient.get(`/market/stocks/${symbol}`)
      .then(setData)
      .catch(() => setNotFound(true));
    apiClient.get(`/market/price-history/${symbol}?days=300`)
      .then(rows => setHistory(
        (Array.isArray(rows) ? rows : []).map(r => ({
          date: r.Date, open: parseFloat(r.Open), high: parseFloat(r.High),
          low: parseFloat(r.Low), close: parseFloat(r.LTP ?? r.Close), volume: parseFloat(r.Volume),
          EMA20: r.EMA20, EMA50: r.EMA50, EMA100: r.EMA100, EMA200: r.EMA200,
        }))
      ))
      .catch(() => setHistory([]));
  }, [symbol]);

  if (notFound) {
    return <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No data for {symbol}</div>;
  }

  if (!data) {
    return <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>Loading…</div>;
  }

  const ltp = data.LTP != null ? parseFloat(data.LTP) : null;
  const change = data.Change != null ? parseFloat(data.Change) : null;
  const changePct = data.ChangePct != null ? parseFloat(data.ChangePct) : null;
  const isUp = change != null && change >= 0;

  const fundamentals = [
    ['Audited PE', data.Audited_PE], ['Forward PE', data.Forward_PE],
    ['Director Holding %', data.Director_Holdings], ['NAV/Price', data.NAV_Quarter_End_],
  ].filter(([, v]) => v != null);

  const trend = describeTrend(history[history.length - 1]);

  const setAlert = async () => {
    if (!alertTarget) return;
    setAlertSaving(true);
    setAlertError('');
    try {
      await apiClient.post('/alerts', { symbol, target_price: parseFloat(alertTarget), direction: alertDir });
      setAlertDone(true);
    } catch (e) { setAlertError(e.message); } finally { setAlertSaving(false); }
  };

  return (
    <div>
      <h1 style={{ fontSize: 18, fontWeight: 700, color: colors.textPrimary, margin: 0 }}>{symbol}</h1>
      <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 2 }}>{data.Sector ?? ''}</div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 16 }}>
        <span data-testid="stock-price" style={{ color: colors.textPrimary, fontSize: 32, fontWeight: 700 }}>
          {ltp != null ? `৳${ltp.toFixed(2)}` : '—'}
        </span>
        {change != null && (
          <span style={{ color: isUp ? colors.green : colors.red, fontSize: 15, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
            {isUp ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
            {isUp ? '+' : ''}{change.toFixed(2)} ({changePct != null ? `${isUp ? '+' : ''}${changePct.toFixed(2)}%` : ''})
          </span>
        )}
      </div>

      {fundamentals.length > 0 && (
        <div style={{ ...card, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 20 }}>
          {fundamentals.map(([label, value]) => (
            <div key={label}>
              <div style={{ color: colors.textSecondary, fontSize: 11 }}>{label}</div>
              <div style={{ color: colors.textPrimary, fontSize: 13, fontWeight: 500, marginTop: 2 }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {history.length > 0 && (
        <div style={{ ...card, marginTop: 20 }}>
          {trend && (
            <div data-testid="trend-summary" style={{ color: trend.bullish ? colors.green : trend.bearish ? colors.red : colors.textSecondary, fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
              {trend.label}
            </div>
          )}
          <CandlestickChart data={history} />
          <VolumeChart data={history} />
        </div>
      )}

      <div style={{ ...card, marginTop: 20 }}>
        <div style={{ color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Bell size={12} /> Set Price Alert
        </div>
        {alertDone ? (
          <div style={{ color: colors.green, fontSize: 13 }}>Alert set successfully!</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <Input placeholder="Target" value={alertTarget} onChange={e => setAlertTarget(e.target.value)} />
              <select value={alertDir} onChange={e => setAlertDir(e.target.value)}
                style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 8px', fontSize: 13 }}>
                <option value="above">Above</option>
                <option value="below">Below</option>
              </select>
              <Btn onClick={setAlert} disabled={alertSaving || !alertTarget}>{alertSaving ? '…' : 'Set'}</Btn>
            </div>
            {alertError && <div style={{ color: colors.red, fontSize: 12 }}>{alertError}</div>}
          </div>
        )}
      </div>
    </div>
  );
};

// Bullish: price trading above all EMAs, with EMAs stacked shortest-to-longest descending.
// Bearish: the mirror image. Anything else is a mixed/sideways market.
function describeTrend(latest) {
  if (!latest) return null;
  const { close, EMA20, EMA50, EMA100, EMA200 } = latest;
  if ([EMA20, EMA50, EMA100, EMA200].some(v => v == null)) return null;

  if (close > EMA20 && EMA20 > EMA50 && EMA50 > EMA100 && EMA100 > EMA200) {
    return { bullish: true, label: 'Bullish — price trading above EMA20/50/100/200, in ascending order' };
  }
  if (close < EMA20 && EMA20 < EMA50 && EMA50 < EMA100 && EMA100 < EMA200) {
    return { bearish: true, label: 'Bearish — price trading below EMA20/50/100/200, in descending order' };
  }
  return { label: 'Mixed — no clear trend across EMA20/50/100/200' };
}
