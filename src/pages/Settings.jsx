import React, { useEffect, useRef, useState } from 'react';
import apiClient from '../api/client';
import { colors } from '../design';
import { Check, Clock, X } from 'lucide-react';
import { useToast } from '../components/Toast';

const Input = ({ label, style, ...props }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
    {label && <label style={{ color: colors.textSecondary, fontSize: 11 }}>{label}</label>}
    <input style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13, outline: 'none', width: '100%', ...style }} {...props} />
  </div>
);

const Btn = ({ variant = 'primary', style, ...props }) => (
  <button style={{
    padding: '7px 16px', borderRadius: 3, fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
    background: variant === 'primary' ? colors.accent : variant === 'ghost' ? colors.surface2 : colors.red,
    color: '#fff', opacity: props.disabled ? 0.5 : 1, ...style,
  }} {...props} />
);

const Toggle = ({ checked, onChange, label }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: colors.textPrimary, fontSize: 13 }}>
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      style={{
        width: 36, height: 20, borderRadius: 10, position: 'relative', cursor: 'pointer', flexShrink: 0,
        background: checked ? colors.accent : colors.surface2, border: `1px solid ${colors.border}`,
        transition: 'background 0.2s', padding: 0,
      }}
    >
      <span style={{ position: 'absolute', top: 2, left: checked ? 18 : 2, width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left 0.2s', display: 'block' }} />
    </button>
    <span onClick={() => onChange(!checked)} style={{ cursor: 'pointer', userSelect: 'none' }}>{label}</span>
  </div>
);

const MEDIUMS = ['telegram', 'whatsapp', 'email', 'web_push'];

const PaymentModal = ({ pkg, pricing, onClose, onDone }) => {
  const [step, setStep] = useState('confirm');
  const [txnId, setTxnId] = useState('');
  const [subId, setSubId] = useState(null);
  const [timeLeft, setTimeLeft] = useState(30 * 60);
  const [submitting, setSubmitting] = useState(false);
  const headingId = 'payment-modal-title';
  const firstFocusRef = useRef(null);
  const toast = useToast();

  useEffect(() => { firstFocusRef.current?.focus(); }, []);

  const price = (() => {
    const w = pricing?.weights ?? [];
    let total = 0;
    for (const m of pkg.medium) {
      const wt = w.find(x => x.dimension === 'medium' && x.key === m);
      if (wt) total += wt.weight_price;
    }
    if (pkg.alert_channel) { const wt = w.find(x => x.key === 'alert'); if (wt) total += wt.weight_price; }
    if (pkg.digest_channel) { const wt = w.find(x => x.key === 'digest'); if (wt) total += wt.weight_price; }
    return total;
  })();

  useEffect(() => {
    if (step !== 'payment') return;
    const t = setInterval(() => setTimeLeft(s => { if (s <= 1) { clearInterval(t); return 0; } return s - 1; }), 1000);
    return () => clearInterval(t);
  }, [step]);

  const proceed = async () => {
    setSubmitting(true);
    try {
      const res = await apiClient.post('/subscriptions', pkg);
      setSubId(res.id);
      setStep('payment');
    } catch (e) { toast.error(e.message || 'Failed to create subscription'); } finally { setSubmitting(false); }
  };

  const submitTxn = async () => {
    if (!txnId.trim()) return;
    setSubmitting(true);
    try {
      await apiClient.post(`/subscriptions/${subId}/transaction`, { transaction_id: txnId.trim() });
      setStep('done');
    } catch (e) { toast.error(e.message || 'Failed to submit transaction'); } finally { setSubmitting(false); }
  };

  const mm = String(Math.floor(timeLeft / 60)).padStart(2, '0');
  const ss = String(timeLeft % 60).padStart(2, '0');

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby={headingId}
        style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 6, padding: 28, width: 420 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
          <span id={headingId} style={{ color: colors.textPrimary, fontSize: 15, fontWeight: 600 }}>
            {step === 'confirm' ? 'Confirm Package' : step === 'payment' ? 'Complete Payment' : 'Submitted!'}
          </span>
          <button ref={firstFocusRef} onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', color: colors.textSecondary, cursor: 'pointer', padding: 4, borderRadius: 2 }}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {step === 'confirm' && (
          <>
            <div style={{ background: colors.surface2, borderRadius: 4, padding: 14, marginBottom: 16 }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 8 }}>Package Summary</div>
              <div style={{ color: colors.textPrimary, fontSize: 13 }}>Channels: {pkg.medium.join(', ')}</div>
              {pkg.alert_channel && <div style={{ color: colors.textPrimary, fontSize: 13 }}>Price Alerts: up to {pkg.alert_cap}/day</div>}
              {pkg.digest_channel && <div style={{ color: colors.textPrimary, fontSize: 13 }}>Daily Digest: {pkg.digest_cadence}</div>}
              <div style={{ color: colors.accent, fontSize: 20, fontWeight: 700, marginTop: 10 }}>৳{price.toFixed(0)}/mo</div>
            </div>
            <Btn onClick={proceed} disabled={submitting} style={{ width: '100%' }}>{submitting ? 'Processing…' : 'Proceed to Payment'}</Btn>
          </>
        )}

        {step === 'payment' && (
          <>
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <div style={{ color: timeLeft < 120 ? colors.red : colors.yellow, fontSize: 24, fontWeight: 700, fontFamily: 'monospace' }}>{mm}:{ss}</div>
              <div style={{ color: colors.textSecondary, fontSize: 12 }}>Time remaining to complete payment</div>
            </div>
            <div style={{ background: colors.surface2, borderRadius: 4, padding: 14, marginBottom: 16 }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 8 }}>Send ৳{price.toFixed(0)} to:</div>
              <div style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 600 }}>bKash: 01XXXXXXXXXX</div>
              <div style={{ color: colors.textPrimary, fontSize: 14, fontWeight: 600 }}>Nagad: 01XXXXXXXXXX</div>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 8 }}>Reference: {subId}</div>
            </div>
            <Input label="Transaction ID" placeholder="e.g. TXN8ABC1234" value={txnId} onChange={e => setTxnId(e.target.value)} style={{ marginBottom: 12 }} />
            <Btn onClick={submitTxn} disabled={submitting || timeLeft === 0 || !txnId} style={{ width: '100%' }}>
              {submitting ? 'Submitting…' : 'Submit Transaction ID'}
            </Btn>
          </>
        )}

        {step === 'done' && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <Check size={40} color={colors.green} style={{ margin: '0 auto 12px' }} />
            <div style={{ color: colors.textPrimary, fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Payment submitted!</div>
            <div style={{ color: colors.textSecondary, fontSize: 13, marginBottom: 20 }}>Admin will verify and activate your subscription. You'll be notified via Telegram.</div>
            <Btn onClick={onDone} style={{ width: '100%' }}>Done</Btn>
          </div>
        )}
      </div>
    </div>
  );
};

export const SettingsPage = () => {
  const [prefs, setPrefs] = useState({ telegram_chat_id: '', whatsapp_number: '', email: '', web_push_subscription: null, channels_enabled: [] });
  const [pkg, setPkg] = useState({ medium: [], alert_channel: true, digest_channel: true, alert_cap: 10, digest_cadence: 'daily' });
  const [pricing, setPricing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [showPayment, setShowPayment] = useState(false);
  const toast = useToast();

  useEffect(() => {
    apiClient.get('/settings/notifications').then(d => setPrefs(p => ({ ...p, ...d }))).catch(() => {});
    apiClient.get('/subscriptions/pricing').then(setPricing).catch(() => {});
  }, []);

  const savePrefs = async () => {
    setSaving(true);
    try {
      await apiClient.put('/settings/notifications', prefs);
      toast.success('Notification preferences saved');
    } catch (e) {
      toast.error(e.message || 'Failed to save preferences');
    } finally { setSaving(false); }
  };

  const toggleMedium = (m) => setPkg(p => ({ ...p, medium: p.medium.includes(m) ? p.medium.filter(x => x !== m) : [...p.medium, m] }));
  const toggleChannel = (m) => setPrefs(p => ({ ...p, channels_enabled: p.channels_enabled.includes(m) ? p.channels_enabled.filter(x => x !== m) : [...p.channels_enabled, m] }));

  return (
    <div style={{ maxWidth: 760 }}>
      <div style={{ color: colors.textPrimary, fontSize: 16, fontWeight: 600, marginBottom: 20 }}>Settings</div>

      {/* Notification preferences */}
      <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4, padding: 20, marginBottom: 16 }}>
        <div style={{ color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 }}>Notification Channels</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
          {MEDIUMS.map(m => <Toggle key={m} label={m.replace('_', ' ')} checked={prefs.channels_enabled.includes(m)} onChange={() => toggleChannel(m)} />)}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <Input label="Telegram Chat ID" value={prefs.telegram_chat_id ?? ''} onChange={e => setPrefs(p => ({ ...p, telegram_chat_id: e.target.value }))} />
          <Input label="WhatsApp Number" value={prefs.whatsapp_number ?? ''} onChange={e => setPrefs(p => ({ ...p, whatsapp_number: e.target.value }))} />
          <Input label="Email" value={prefs.email ?? ''} onChange={e => setPrefs(p => ({ ...p, email: e.target.value }))} />
        </div>
        <Btn onClick={savePrefs} disabled={saving}>{saving ? 'Saving…' : 'Save Preferences'}</Btn>
      </div>

      {/* Package builder */}
      <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4, padding: 20 }}>
        <div style={{ color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 }}>Subscription Package</div>

        <div style={{ marginBottom: 14 }}>
          <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 8 }}>Delivery Channels</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {MEDIUMS.map(m => (
              <button key={m} onClick={() => toggleMedium(m)} style={{
                padding: '5px 12px', borderRadius: 3, fontSize: 12, fontWeight: 500, cursor: 'pointer', border: `1px solid ${pkg.medium.includes(m) ? colors.accent : colors.border}`,
                background: pkg.medium.includes(m) ? `${colors.accent}22` : colors.surface2, color: pkg.medium.includes(m) ? colors.accent : colors.textSecondary,
              }}>{m.replace('_', ' ')}</button>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
          <div>
            <Toggle label="Price Alerts" checked={pkg.alert_channel} onChange={v => setPkg(p => ({ ...p, alert_channel: v }))} />
            {pkg.alert_channel && (
              <div style={{ marginTop: 8 }}>
                <div style={{ color: colors.textSecondary, fontSize: 11, marginBottom: 4 }}>Max alerts/day</div>
                <input type="range" min={1} max={100} value={pkg.alert_cap} onChange={e => setPkg(p => ({ ...p, alert_cap: parseInt(e.target.value) }))}
                  style={{ width: '100%', accentColor: colors.accent }} />
                <span style={{ color: colors.textPrimary, fontSize: 13 }}>{pkg.alert_cap}</span>
              </div>
            )}
          </div>
          <div>
            <Toggle label="Daily Digest" checked={pkg.digest_channel} onChange={v => setPkg(p => ({ ...p, digest_channel: v }))} />
            {pkg.digest_channel && (
              <div style={{ marginTop: 8 }}>
                <div style={{ color: colors.textSecondary, fontSize: 11, marginBottom: 4 }}>Frequency</div>
                <select value={pkg.digest_cadence} onChange={e => setPkg(p => ({ ...p, digest_cadence: e.target.value }))}
                  style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: colors.textPrimary, padding: '6px 10px', fontSize: 13 }}>
                  <option value="daily">Daily</option>
                  <option value="alternate">Every 2 days</option>
                  <option value="weekly">Weekly</option>
                </select>
              </div>
            )}
          </div>
        </div>

        {pricing && (
          <div style={{ background: colors.surface2, borderRadius: 4, padding: 12, marginBottom: 14 }}>
            <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 4 }}>Estimated Price</div>
            <div style={{ color: colors.accent, fontSize: 20, fontWeight: 700 }}>
              ৳{(() => {
                let total = 0;
                for (const m of pkg.medium) { const w = pricing.weights?.find(x => x.dimension === 'medium' && x.key === m); if (w) total += w.weight_price; }
                if (pkg.alert_channel) { const w = pricing.weights?.find(x => x.key === 'alert'); if (w) total += w.weight_price; }
                if (pkg.digest_channel) { const w = pricing.weights?.find(x => x.key === 'digest'); if (w) total += w.weight_price; }
                return total.toFixed(0);
              })()}/mo
            </div>
          </div>
        )}

        {pricing?.bundles?.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 8 }}>Or choose a bundle</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {pricing.bundles.map(b => (
                <div key={b.name} style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '10px 14px', minWidth: 120 }}>
                  <div style={{ color: colors.textPrimary, fontSize: 13, fontWeight: 600 }}>{b.name}</div>
                  <div style={{ color: colors.accent, fontSize: 16, fontWeight: 700, marginTop: 4 }}>৳{b.price}/mo</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <Btn onClick={() => setShowPayment(true)} disabled={pkg.medium.length === 0}>Subscribe & Pay</Btn>
      </div>

      {showPayment && <PaymentModal pkg={pkg} pricing={pricing} onClose={() => setShowPayment(false)} onDone={() => setShowPayment(false)} />}
    </div>
  );
};
