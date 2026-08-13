import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'light' | 'dark';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

// Ported from main's ThemeContext (#82). Drives dark mode through the
// `data-theme` attribute on <html> — index.css's :root is the dark palette by
// default (#87: dark is the product default, TradingView-style) and
// [data-theme='light'] is the explicit opt-out.
const ThemeContext = createContext<ThemeContextValue>({
  theme: 'dark',
  toggleTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

function initialTheme(): Theme {
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('theme') : null;
  return stored === 'dark' || stored === 'light' ? stored : 'dark';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>
  );
}
