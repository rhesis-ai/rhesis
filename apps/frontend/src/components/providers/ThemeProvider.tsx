'use client';

import * as React from 'react';
import {
  ThemeProvider as MuiThemeProvider,
  createTheme,
} from '@mui/material/styles';
import { getDesignTokens } from '../../styles/theme';
import CssBaseline from '@mui/material/CssBaseline';

export const ColorModeContext = React.createContext({
  toggleColorMode: () => {},
  mode: 'light' as 'light' | 'dark',
});

interface ThemeContextProviderProps {
  children: React.ReactNode;
  disableTransitionOnChange?: boolean;
  initialMode?: 'light' | 'dark';
}

const THEME_MODE_KEY = 'theme-mode';
const THEME_MODE_COOKIE = 'theme-mode';

function persistThemeMode(mode: 'light' | 'dark') {
  localStorage.setItem(THEME_MODE_KEY, mode);
  document.documentElement.setAttribute('data-theme-mode', mode);
  document.cookie = `${THEME_MODE_COOKIE}=${mode};path=/;max-age=31536000;SameSite=Lax`;
}

export default function ThemeContextProvider({
  children,
  disableTransitionOnChange = false,
  initialMode = 'light',
}: ThemeContextProviderProps) {
  const [mode, setMode] = React.useState<'light' | 'dark'>(initialMode);

  React.useLayoutEffect(() => {
    const attr = document.documentElement.getAttribute('data-theme-mode');
    if (attr === 'light' || attr === 'dark') {
      setMode(attr);
      return;
    }

    const storedMode = localStorage.getItem(THEME_MODE_KEY);
    if (storedMode === 'light' || storedMode === 'dark') {
      setMode(storedMode);
      document.documentElement.setAttribute('data-theme-mode', storedMode);
      return;
    }

    const systemMode = window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
    setMode(systemMode);
    document.documentElement.setAttribute('data-theme-mode', systemMode);
  }, []);

  React.useEffect(() => {
    const storedMode = localStorage.getItem(THEME_MODE_KEY);
    if (storedMode) return;

    const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      const newMode = e.matches ? 'dark' : 'light';
      setMode(newMode);
      document.documentElement.setAttribute('data-theme-mode', newMode);
    };
    darkModeQuery.addEventListener('change', handler);
    return () => darkModeQuery.removeEventListener('change', handler);
  }, []);

  const colorMode = React.useMemo(
    () => ({
      toggleColorMode: () => {
        if (disableTransitionOnChange) {
          document.documentElement.style.setProperty('transition', 'none');
          document.body.style.setProperty('transition', 'none');
        }

        setMode(prevMode => {
          const newMode = prevMode === 'light' ? 'dark' : 'light';
          persistThemeMode(newMode);
          return newMode;
        });

        if (disableTransitionOnChange) {
          requestAnimationFrame(() => {
            document.documentElement.style.removeProperty('transition');
            document.body.style.removeProperty('transition');
          });
        }
      },
      mode,
    }),
    [mode, disableTransitionOnChange]
  );

  const theme = React.useMemo(() => createTheme(getDesignTokens(mode)), [mode]);

  return (
    <ColorModeContext.Provider value={colorMode}>
      <MuiThemeProvider
        theme={theme}
        disableTransitionOnChange={disableTransitionOnChange}
      >
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ColorModeContext.Provider>
  );
}
