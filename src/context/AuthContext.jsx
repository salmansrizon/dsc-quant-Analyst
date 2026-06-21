import React, { createContext, useState, useEffect, useContext } from 'react';
import apiClient from '../api/client';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedToken = localStorage.getItem('access_token');
    if (savedToken) {
      apiClient.setToken(savedToken);
      handleMe();
    } else {
      setLoading(false);
    }
  }, []);

  const handleMe = async () => {
    try {
      const data = await apiClient.get('/auth/me');
      setUser(data);
      setLoading(false);
    } catch {
      logout();
    }
  };

  const login = async (email, password) => {
    const data = await apiClient.post('/auth/login', { email, password });
    localStorage.setItem('access_token', data.access_token);
    apiClient.setToken(data.access_token);
    setUser(data.user);
  };

  const signup = async (details) => {
    const data = await apiClient.post('/auth/signup', details);
    localStorage.setItem('access_token', data.access_token);
    apiClient.setToken(data.access_token);
    setUser(data.user);
  };

  const reloadUser = () => {
    setLoading(true);
    handleMe();
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
    setUser(null);
    setLoading(false);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout, reloadUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
