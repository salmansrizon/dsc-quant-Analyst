import React, { createContext, useContext, useEffect, useState } from 'react';

type Theme = 'light' | 'dark';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

// Ported from main's ThemeContext (#82). Drives dark mode through the
// `data-theme` attribute on <html> — index.css defines the [data-theme='dark']
// CSS-variable overrides, so this works with the repo's actual styling (there
// is no Tailwind here; utility-class dark: variants would be inert).
const ThemeContext = createContext<ThemeContextValue>({
  theme: 'light',
  toggleTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

function initialTheme(): Theme {
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('theme') : null;
  return stored === 'dark' || stored === 'light' ? stored : 'light';
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
