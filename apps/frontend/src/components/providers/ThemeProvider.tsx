'use client';

import * as React from 'react';
import {
  ThemeProvider as MuiThemeProvider,
  createTheme,
} from '@mui/material/styles';
import { getDesignTokens } from '../../styles/theme';
import CssBaseline from '@mui/material/CssBaseline';

// Create a context for theme mode
export const ColorModeContext = React.createContext({
  toggleColorMode: () => {},
  mode: 'light' as 'light' | 'dark',
});

interface ThemeContextProviderProps {
  children: React.ReactNode;
  disableTransitionOnChange?: boolean;
}

const THEME_MODE_KEY = 'theme-mode';

export default function ThemeContextProvider({
  children,
  disableTransitionOnChange = false,
}: ThemeContextProviderProps) {
  const [mode, setMode] = React.useState<'light' | 'dark'>('light');
  const [mounted, setMounted] = React.useState(false);

  React.useLayoutEffect(() => {
    const attr = document.documentElement.getAttribute('data-theme-mode');
    if (attr === 'light' || attr === 'dark') {
      setMode(attr);
    }
    setMounted(true);
  }, []);

  React.useEffect(() => {
    const storedMode = localStorage.getItem(THEME_MODE_KEY);
    if (!storedMode) {
      const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
      const handler = (e: MediaQueryListEvent) => {
        const newMode = e.matches ? 'dark' : 'light';
        setMode(newMode);
        document.documentElement.setAttribute('data-theme-mode', newMode);
      };
      darkModeQuery.addEventListener('change', handler);
      return () => darkModeQuery.removeEventListener('change', handler);
    }
  }, []);

  const colorMode = React.useMemo(
    () => ({
      toggleColorMode: () => {
        if (disableTransitionOnChange) {
          // Disable all transitions temporarily
          document.documentElement.style.setProperty('transition', 'none');
          document.body.style.setProperty('transition', 'none');
        }

        setMode(prevMode => {
          const newMode = prevMode === 'light' ? 'dark' : 'light';
          localStorage.setItem(THEME_MODE_KEY, newMode);
          document.documentElement.setAttribute('data-theme-mode', newMode);
          return newMode;
        });

        if (disableTransitionOnChange) {
          // Re-enable transitions after the theme change
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
        <div
          style={{
            visibility: mounted ? 'visible' : 'hidden',
          }}
          suppressHydrationWarning
        >
          {children}
        </div>
      </MuiThemeProvider>
    </ColorModeContext.Provider>
  );
}
