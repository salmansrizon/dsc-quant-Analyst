import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, TrendingUp, PieChart, Bell, Users, Settings, BarChart2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { colors } from '../design';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/watchlist', icon: TrendingUp, label: 'Watchlist' },
  { to: '/portfolio', icon: PieChart, label: 'Portfolio' },
  { to: '/alerts', icon: Bell, label: 'Alerts' },
];

const NavItem = ({ to, icon: Icon, label, end }) => (
  <NavLink
    to={to}
    end={end}
    className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`}
  >
    <Icon size={17} aria-hidden="true" style={{ flexShrink: 0 }} />
    {label}
  </NavLink>
);

const initials = (name = '') =>
  name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?';

export const Sidebar = () => {
  const { user } = useAuth();

  return (
    <aside
      className="ds-sidebar"
      style={{
        width: 224,
        background: colors.surface,
        borderRight: `1px solid ${colors.border}`,
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        height: '100vh',
        position: 'sticky',
        top: 0,
      }}
    >
      {/* Brand */}
      <div style={{ padding: '20px 16px 18px', borderBottom: `1px solid ${colors.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Logo mark */}
          <div style={{
            width: 30, height: 30, borderRadius: 8, flexShrink: 0,
            background: 'var(--gradient-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(59,126,248,0.35)',
          }}>
            <BarChart2 size={16} color="#fff" aria-hidden="true" />
          </div>
          <span style={{
            fontSize: 15, fontWeight: 700, letterSpacing: -0.4,
            color: colors.textPrimary,
          }}>
            DSC <span style={{ color: colors.accent }}>Quant</span>
          </span>
        </div>
      </div>

      {/* Primary nav */}
      <nav aria-label="Main navigation" style={{ flex: 1, padding: '10px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {NAV_ITEMS.map(item => (
          <NavItem key={item.to} {...item} />
        ))}
        {user?.role === 'admin' && (
          <NavItem to="/admin" icon={Users} label="Admin" />
        )}
      </nav>

      {/* Bottom — Settings + user */}
      <div style={{ padding: '8px 8px 16px', borderTop: `1px solid ${colors.border}` }}>
        <NavItem to="/settings" icon={Settings} label="Settings" />

        {user && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 12px', marginTop: 4,
          }}>
            {/* Avatar */}
            <div style={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
              background: 'var(--gradient-brand)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: '#fff',
            }}>
              {initials(user.full_name)}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ color: colors.textPrimary, fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.full_name}
              </div>
              <div style={{ color: colors.textSecondary, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user.email || user.role}
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
