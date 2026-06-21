import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, TrendingUp, PieChart, Bell, Users, Settings } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Sidebar = () => {
  const { user } = useAuth();
  return (
    <aside className="w-64 bg-gray-900 text-white min-h-screen p-4">
      <nav className="space-y-2">
        <NavLink to="/" className="flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-800">
          <LayoutDashboard size={20} /> Dashboard
        </NavLink>
        <NavLink to="/watchlist" className="flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-800">
          <TrendingUp size={20} /> Watchlist
        </NavLink>
        <NavLink to="/portfolio" className="flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-800">
          <PieChart size={20} /> Portfolio
        </NavLink>
        <NavLink to="/alerts" className="flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-800">
          <Bell size={20} /> Alerts
        </NavLink>
        {user?.role === 'admin' && (
          <NavLink to="/admin" className="flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-800">
            <Users size={20} /> Admin
          </NavLink>
        )}
      </nav>
    </aside>
  );
};