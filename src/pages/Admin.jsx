import React, { useEffect, useState } from 'react';
import apiClient from '../api/client';
import { colors } from '../design';
import { CheckCircle, XCircle, Clock, Users, Package, Activity } from 'lucide-react';

const Btn = ({ variant = 'primary', style, ...props }) => (
  <button style={{
    padding: '5px 12px', borderRadius: 3, fontSize: 12, fontWeight: 500, cursor: 'pointer', border: 'none',
    background: variant === 'primary' ? colors.accent : variant === 'danger' ? colors.red : variant === 'success' ? colors.green : colors.surface2,
    color: '#fff', opacity: props.disabled ? 0.5 : 1, ...style,
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

const StatusBadge = ({ status }) => {
  const cfg = {
    pending: { color: colors.yellow, icon: <Clock size={12} /> },
    active: { color: colors.green, icon: <CheckCircle size={12} /> },
    rejected: { color: colors.red, icon: <XCircle size={12} /> },
  }[status] ?? { color: colors.textSecondary, icon: null };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: cfg.color, fontSize: 12, fontWeight: 500 }}>
      {cfg.icon}{status}
    </span>
  );
};

const SubscriptionQueue = () => {
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => apiClient.get('/admin/subscriptions').then(d => { setSubs(Array.isArray(d) ? d : []); setLoading(false); }).catch(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const decide = async (id, approve) => {
    await apiClient.post(`/admin/subscriptions/${id}/${approve ? 'approve' : 'reject'}`);
    load();
  };

  if (loading) return <div style={{ color: colors.textSecondary, padding: 24 }}>Loading…</div>;

  return (
    <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px 80px 120px auto', padding: '8px 16px', borderBottom: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
        <span>User / Package</span><span>Transaction</span><span>Status</span><span>Submitted</span><span>Actions</span>
      </div>
      {subs.length === 0 && <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No subscriptions</div>}
      {subs.map(sub => (
        <div key={sub.id} style={{ display: 'grid', gridTemplateColumns: '1fr 120px 80px 120px auto', padding: '10px 16px', borderBottom: `1px solid ${colors.border}`, alignItems: 'center', gap: 8 }}>
          <div>
            <div style={{ color: colors.textPrimary, fontSize: 13 }}>{sub.user_id}</div>
            <div style={{ color: colors.textSecondary, fontSize: 11 }}>
              {(sub.medium ?? []).join(', ')} · {sub.digest_cadence}
            </div>
          </div>
          <span style={{ color: sub.transaction_id ? colors.textPrimary : colors.textSecondary, fontSize: 12, fontFamily: 'monospace' }}>
            {sub.transaction_id ?? '—'}
          </span>
          <StatusBadge status={sub.status} />
          <span style={{ color: colors.textSecondary, fontSize: 11 }}>
            {sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : '—'}
          </span>
          {sub.status === 'pending' && sub.transaction_id && (
            <div style={{ display: 'flex', gap: 4 }}>
              <Btn variant="success" onClick={() => decide(sub.id, true)}>Approve</Btn>
              <Btn variant="danger" onClick={() => decide(sub.id, false)}>Reject</Btn>
            </div>
          )}
          {sub.status !== 'pending' && <span />}
        </div>
      ))}
    </div>
  );
};

const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const load = () => apiClient.get('/admin/users').then(d => setUsers(Array.isArray(d) ? d : [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const setRole = async (id, role) => { await apiClient.put(`/admin/users/${id}`, { role }); load(); };

  return (
    <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 120px 80px', padding: '8px 16px', borderBottom: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1 }}>
        <span>Name</span><span>Email</span><span>Phone</span><span>Role</span>
      </div>
      {users.length === 0 && <div style={{ color: colors.textSecondary, fontSize: 13, padding: 24, textAlign: 'center' }}>No users</div>}
      {users.map(u => (
        <div key={u.id} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 120px 80px', padding: '10px 16px', borderBottom: `1px solid ${colors.border}`, alignItems: 'center' }}>
          <span style={{ color: colors.textPrimary, fontSize: 13 }}>{u.full_name}</span>
          <span style={{ color: colors.textSecondary, fontSize: 12 }}>{u.email}</span>
          <span style={{ color: colors.textSecondary, fontSize: 12 }}>{u.phone}</span>
          <select value={u.role} onChange={e => setRole(u.id, e.target.value)}
            style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3, color: u.role === 'admin' ? colors.accent : colors.textPrimary, padding: '4px 8px', fontSize: 12 }}>
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
        </div>
      ))}
    </div>
  );
};

const PipelineStatus = () => {
  const steps = [
    { name: 'dataGrid.py', label: 'Market Data' },
    { name: 'priceArchive.py', label: 'Price Archive' },
    { name: 'announcement.py', label: 'Announcements' },
    { name: 'refresh_cache.py', label: 'Cache Refresh' },
    { name: 'alert_checker.py', label: 'Alert Checker' },
  ];
  return (
    <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4, padding: 20 }}>
      <div style={{ color: colors.textSecondary, fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 14 }}>Daily Pipeline (Sun–Thu 2:30 PM BDT)</div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {steps.map((s, i) => (
          <React.Fragment key={s.name}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 4, padding: '8px 12px' }}>
                <Activity size={16} color={colors.accent} />
                <div style={{ color: colors.textPrimary, fontSize: 12, marginTop: 4, whiteSpace: 'nowrap' }}>{s.label}</div>
                <div style={{ color: colors.textSecondary, fontSize: 10 }}>{s.name}</div>
              </div>
            </div>
            {i < steps.length - 1 && <div style={{ color: colors.border, fontSize: 18 }}>→</div>}
          </React.Fragment>
        ))}
      </div>
      <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 14 }}>
        Scheduled via GitHub Actions cron <code style={{ color: colors.textPrimary }}>30 8 * * 0-4</code> (UTC = 2:30 PM BDT)
      </div>
    </div>
  );
};

export const AdminPage = () => {
  const [tab, setTab] = useState('subscriptions');

  return (
    <div>
      <div style={{ color: colors.textPrimary, fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Admin</div>
      <div style={{ display: 'flex', borderBottom: `1px solid ${colors.border}`, marginBottom: 16 }}>
        <Tab active={tab === 'subscriptions'} onClick={() => setTab('subscriptions')}><Package size={14} style={{ marginRight: 4, display: 'inline' }} />Subscription Queue</Tab>
        <Tab active={tab === 'users'} onClick={() => setTab('users')}><Users size={14} style={{ marginRight: 4, display: 'inline' }} />Users</Tab>
        <Tab active={tab === 'pipeline'} onClick={() => setTab('pipeline')}><Activity size={14} style={{ marginRight: 4, display: 'inline' }} />Pipeline</Tab>
      </div>
      {tab === 'subscriptions' && <SubscriptionQueue />}
      {tab === 'users' && <UserManagement />}
      {tab === 'pipeline' && <PipelineStatus />}
    </div>
  );
};
