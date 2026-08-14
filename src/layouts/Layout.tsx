import { useContext } from 'react';
import type { AxiosInstance } from 'axios';
import { AnimatePresence, motion } from 'motion/react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Moon, Sun } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { pageTransition } from '../design/motion';
import ProfileNudge from '../components/ProfileQuiz/ProfileNudge';

const navItems = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/portfolio', label: 'Portfolio' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/screener', label: 'Screener' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/settings', label: 'Settings' },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive
      ? 'text-indigo-700 bg-indigo-50'
      : 'text-gray-700 hover:text-indigo-600 hover:bg-indigo-50'
  }`;

function Layout({ client }: { client: AxiosInstance }) {
  const { user, logout } = useContext(AuthContext);
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

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
                onClick={toggleTheme}
                aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                className="p-2 rounded-md text-gray-700 hover:bg-indigo-50"
              >
                {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </button>
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
        <ProfileNudge client={client} />
        {/* #87: theme/route-transition motion trigger — fades page content on
            route change, scoped exactly to what the decision record allows. */}
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageTransition}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default Layout;
