import { useContext } from 'react';
import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { AuthContext } from '../../context/AuthContext';

interface PrivateRouteProps {
  children: ReactNode;
  /** When true, also require the loaded user to have the admin role. */
  adminOnly?: boolean;
}

/**
 * Route guard: renders children when a session token is present, otherwise
 * redirects to /login. Token presence is the source of truth (AuthContext
 * validates it against /auth/me on mount). With `adminOnly`, a non-admin is
 * sent to the dashboard even with a valid token (the backend also enforces
 * this on every /api/admin/* route).
 */
export default function PrivateRoute({ children, adminOnly = false }: PrivateRouteProps) {
  const { token, user } = useContext(AuthContext);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (adminOnly) {
    if (user === null) {
      return null; // still resolving /auth/me — don't flash the panel
    }
    if (user.role !== 'admin') {
      return <Navigate to="/" replace />;
    }
  }
  return <>{children}</>;
}
