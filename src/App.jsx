import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './components/Toast';
import { ThemeProvider } from './context/ThemeContext';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AdminRoute } from './components/AdminRoute';
import { DashboardPage } from './pages/Dashboard';
import { LoginPage } from './pages/Login';
import { SignupPage } from './pages/Signup';
import { AdminPage } from './pages/Admin';
import { WatchlistPage } from './pages/Watchlist';
import { PortfolioPage } from './pages/Portfolio';
import { AlertsPage } from './pages/Alerts';
import { SettingsPage } from './pages/Settings';
import { colors } from './design';

const Shell = ({ children }) => (
  <div style={{ display: 'flex', height: '100vh', background: colors.bg, fontFamily: "'Ubuntu', -apple-system, BlinkMacSystemFont, sans-serif", fontSize: 14, color: colors.textPrimary }}>
    <Sidebar />
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
      <Topbar />
      <main style={{ flex: 1, overflow: 'auto', padding: '18px 20px' }}>
        {children}
      </main>
    </div>
  </div>
);

export default function App() {
  return (
    <ThemeProvider>
    <ToastProvider>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Shell>
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/watchlist" element={<WatchlistPage />} />
                    <Route path="/portfolio" element={<PortfolioPage />} />
                    <Route path="/alerts" element={<AlertsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route
                      path="/admin/*"
                      element={
                        <AdminRoute>
                          <AdminPage />
                        </AdminRoute>
                      }
                    />
                  </Routes>
                </Shell>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ToastProvider>
    </ThemeProvider>
  );
}
