import React from 'react';
import { useAuth } from '../context/AuthContext';

export const DashboardPage = () => {
  const { user } = useAuth();
  return (
    <div>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p>Welcome back, {user?.full_name}!</p>
    </div>
  );
};