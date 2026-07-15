import type { AxiosInstance } from 'axios';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import defaultClient from './api/client';
import { AuthProvider } from './context/AuthContext';
import Layout from './layouts/Layout';
import PrivateRoute from './components/PrivateRoute/PrivateRoute';
import Login from './components/Login/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import Watchlist from './pages/Watchlist';
import AlertsPage from './pages/AlertsPage';
import AdminPanel from './pages/AdminPanel';

interface AppProps {
  client?: AxiosInstance;
}

function App({ client = defaultClient }: AppProps) {
  return (
    <AuthProvider client={client}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup client={client} />} />

          <Route
            element={
              <PrivateRoute>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route path="/" element={<Dashboard client={client} />} />
            <Route path="/portfolio" element={<Portfolio client={client} />} />
            <Route path="/watchlist" element={<Watchlist client={client} />} />
            <Route path="/alerts" element={<AlertsPage client={client} />} />
          </Route>

          <Route
            path="/admin"
            element={
              <PrivateRoute adminOnly>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route index element={<AdminPanel client={client} />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
