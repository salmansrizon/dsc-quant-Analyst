import { useContext } from 'react';
import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { AuthContext } from '../../context/AuthContext';

interface PrivateRouteProps {
  children: ReactNode;
}

/**
 * Route guard: renders children when a session token is present, otherwise
 * redirects to /login. Token presence is the source of truth (AuthContext
 * validates it against /auth/me on mount).
 */
export default function PrivateRoute({ children }: PrivateRouteProps) {
  const { token } = useContext(AuthContext);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
