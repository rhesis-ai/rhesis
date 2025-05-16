'use client';

import * as React from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import { createTheme, Theme } from '@mui/material/styles';
import { getDesignTokens } from '../../styles/theme';
import CssBaseline from '@mui/material/CssBaseline';

// Create a context for theme mode
export const ColorModeContext = React.createContext({
  toggleColorMode: () => {},
  mode: 'light' as 'light' | 'dark'
});

interface ThemeContextProviderProps {
  children: React.ReactNode;
  disableTransitionOnChange?: boolean;
}

const THEME_MODE_KEY = 'theme-mode';

export default function ThemeContextProvider({ 
  children,
  disableTransitionOnChange = false 
}: ThemeContextProviderProps) {
  const [mode, setMode] = React.useState<'light' | 'dark'>('light');
  
  React.useEffect(() => {
    // First check localStorage
    const storedMode = localStorage.getItem(THEME_MODE_KEY) as 'light' | 'dark' | null;
    if (storedMode) {
      setMode(storedMode);
      return;
    }

    // If no stored preference, check system preference
    const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
    setMode(darkModeQuery.matches ? 'dark' : 'light');

    // Listen for changes in system preference
    const handler = (e: MediaQueryListEvent) => {
      setMode(e.matches ? 'dark' : 'light');
    };
    darkModeQuery.addEventListener('change', handler);
    return () => darkModeQuery.removeEventListener('change', handler);
  }, []);

  const colorMode = React.useMemo(
    () => ({
      toggleColorMode: () => {
        if (disableTransitionOnChange) {
          // Disable all transitions temporarily
          document.documentElement.style.setProperty('transition', 'none');
          document.body.style.setProperty('transition', 'none');
        }

        setMode((prevMode) => {
          const newMode = prevMode === 'light' ? 'dark' : 'light';
          localStorage.setItem(THEME_MODE_KEY, newMode);
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

  const theme = React.useMemo(
    () => createTheme(getDesignTokens(mode)),
    [mode]
  );

  return (
    <ColorModeContext.Provider value={colorMode}>
      <MuiThemeProvider theme={theme} disableTransitionOnChange={disableTransitionOnChange}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ColorModeContext.Provider>
  );
} 