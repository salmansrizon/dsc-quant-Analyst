import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext, type User } from '../../../context/AuthContext';
import PrivateRoute from '../PrivateRoute';

function renderGuard(
  token: string | null,
  user: User | null = null,
  adminOnly = false,
) {
  const ctx = { user, token, login: async () => {}, logout: () => {} };
  return render(
    <AuthContext.Provider value={ctx}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <PrivateRoute adminOnly={adminOnly}>
                <div>secret</div>
              </PrivateRoute>
            }
          />
          <Route path="/login" element={<div>login page</div>} />
          <Route path="/home" element={<div>home page</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

const renderWithToken = (token: string | null) => renderGuard(token);
const admin: User = { id: '1', email: 'a@x.com', role: 'admin' };
const regular: User = { id: '2', email: 'b@x.com', role: 'user' };

describe('PrivateRoute', () => {
  it('renders children when a token is present', () => {
    renderWithToken('jwt-token');
    expect(screen.getByText('secret')).toBeInTheDocument();
  });

  it('redirects to /login when there is no token', () => {
    renderWithToken(null);
    expect(screen.getByText('login page')).toBeInTheDocument();
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
  });

  it('renders admin content for an admin user', () => {
    renderGuard('jwt', admin, true);
    expect(screen.getByText('secret')).toBeInTheDocument();
  });

  it('blocks a non-admin from an adminOnly route', () => {
    renderGuard('jwt', regular, true);
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
  });

  it('renders nothing while the user is still loading on an adminOnly route', () => {
    renderGuard('jwt', null, true);
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
  });
});
