import React, { createContext, useState, useEffect } from 'react';
import type { AxiosInstance } from 'axios';

interface AuthContextProps {
  user: any;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextProps>({
  user: null,
  token: null,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ client, children }: { client: AxiosInstance; children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    if (token) {
      client.get('/auth/me').then((res) => setUser(res.data))
        .catch(() => {setToken(null); localStorage.removeItem('token');});
    }
  }, [token, client]);

  const login = async (email: string, password: string) => {
    const res = await client.post('/auth/login', { email, password });
    const { access_token, user } = res.data;
    setToken(access_token);
    localStorage.setItem('token', access_token);
    setUser(user);
  };

  const logout = () => {
    setToken(null); setUser(null); localStorage.removeItem('token');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>{children}</AuthContext.Provider>
  );
}
