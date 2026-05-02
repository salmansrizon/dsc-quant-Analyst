import { useAuth } from '../context/AuthContext';
import { NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  TrendingUp, 
  Megaphone, 
  Star, 
  Briefcase, 
  Bell, 
  Users, 
  Settings, 
  LogOut 
} from 'lucide-react';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">
          <TrendingUp size={20} />
        </div>
        <h1>DSC Quant</h1>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Market</div>
        <NavLink to="/" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`} end>
          <LayoutDashboard size={18} className="icon" /> Dashboard
        </NavLink>
        <NavLink to="/symbols" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <TrendingUp size={18} className="icon" /> Symbols
        </NavLink>
        <NavLink to="/announcements" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Megaphone size={18} className="icon" /> Announcements
        </NavLink>

        <div className="sidebar-section-label">Portfolio</div>
        <NavLink to="/watchlist" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Star size={18} className="icon" /> Watchlist
        </NavLink>
        <NavLink to="/portfolio" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Briefcase size={18} className="icon" /> Portfolio
        </NavLink>
        <NavLink to="/alerts" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
          <Bell size={18} className="icon" /> Price Alerts
        </NavLink>

        {isAdmin && (
          <>
            <div className="sidebar-section-label">Admin</div>
            <NavLink to="/admin/users" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
              <Users size={18} className="icon" /> Users
            </NavLink>
            <NavLink to="/admin/pipeline" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
              <Settings size={18} className="icon" /> Pipeline
            </NavLink>
          </>
        )}
      </nav>

      <div style={{ padding: 'var(--space-4)', borderTop: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <div className="topbar-avatar">{user?.full_name?.[0] || '?'}</div>
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: 'var(--font-size-sm)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.full_name}</div>
            <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>{user?.role}</div>
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={handleLogout} style={{ width: '100%', justifyContent: 'flex-start' }}>
          <LogOut size={14} /> Logout
        </button>
      </div>
    </aside>
  );
}
