import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogOut, Sun, Moon } from 'lucide-react';
import { colors } from '../design';
import { SymbolSearch } from './SymbolSearch';
import { useTheme } from '../context/ThemeContext';

export const Topbar = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const openSymbol = (sym) => {
    const symbol = (sym || '').trim().toUpperCase();
    if (!symbol) return;
    navigate(`/stocks/${symbol}`);
    setQuery('');
  };

  return (
    <>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 48, background: colors.surface, borderBottom: `1px solid ${colors.border}`, padding: '0 16px', flexShrink: 0, zIndex: 50 }}>
        <div style={{ flex: 1, maxWidth: 340 }}>
          <SymbolSearch
            value={query}
            onChange={setQuery}
            onSelect={(row) => openSymbol(row.Symbol)}
            onSubmitRaw={(q) => openSymbol(q)}
            placeholder="Search symbol…"
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {user && (
            <span style={{ color: colors.textSecondary, fontSize: 13 }}>{user.full_name}</span>
          )}
          <button
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            style={{ background: 'none', border: 'none', color: colors.textSecondary, cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '6px 8px', borderRadius: 3 }}
          >
            {theme === 'dark' ? <Sun size={15} aria-hidden="true" /> : <Moon size={15} aria-hidden="true" />}
          </button>
          <button onClick={logout} aria-label="Sign out" title="Sign out" style={{ background: 'none', border: 'none', color: colors.textSecondary, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, padding: '6px 8px', borderRadius: 3 }}>
            <LogOut size={15} aria-hidden="true" />
          </button>
        </div>
      </header>
    </>
  );
};
