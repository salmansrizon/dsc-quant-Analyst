import { useContext } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

const navItems = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/alerts', label: 'Alerts' },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive
      ? 'text-indigo-700 bg-indigo-50'
      : 'text-gray-700 hover:text-indigo-600 hover:bg-indigo-50'
  }`;

function Layout() {
  const { user, logout } = useContext(AuthContext);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <nav
          className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"
          aria-label="Main navigation"
        >
          <div className="flex justify-between h-16 items-center">
            <div className="flex items-center gap-4">
              <NavLink to="/" className="text-xl font-bold text-indigo-600">
                DSC Quant Analyst
              </NavLink>
              <div className="flex items-center space-x-1">
                {navItems.map((item) => (
                  <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
                    {item.label}
                  </NavLink>
                ))}
                {user?.role === 'admin' && (
                  <NavLink to="/admin" className={linkClass}>
                    Admin
                  </NavLink>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {user?.email && (
                <span className="text-sm text-gray-500">{user.email}</span>
              )}
              <button
                type="button"
                onClick={handleLogout}
                className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-red-600 hover:bg-red-50"
              >
                Log out
              </button>
            </div>
          </div>
        </nav>
      </header>
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}

export default Layout;
