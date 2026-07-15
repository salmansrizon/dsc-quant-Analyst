import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../../../context/AuthContext';
import PrivateRoute from '../PrivateRoute';

function renderWithToken(token: string | null) {
  const ctx = { user: null, token, login: async () => {}, logout: () => {} };
  return render(
    <AuthContext.Provider value={ctx}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <PrivateRoute>
                <div>secret</div>
              </PrivateRoute>
            }
          />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

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
});
