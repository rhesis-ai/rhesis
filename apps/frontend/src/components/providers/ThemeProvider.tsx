'use client';

import * as React from 'react';
import {
  ThemeProvider as MuiThemeProvider,
  createTheme,
} from '@mui/material/styles';
import { getDesignTokens, type BrandColors } from '../../styles/theme';

export const ColorModeContext = React.createContext({
  toggleColorMode: () => {},
  mode: 'light' as 'light' | 'dark',
});

interface ThemeContextProviderProps {
  children: React.ReactNode;
  disableTransitionOnChange?: boolean;
  initialMode?: 'light' | 'dark';
  /**
   * Validated `BRAND_PRIMARY_COLOR` / `BRAND_SECONDARY_COLOR` for white-label
   * deployments, passed down from the root layout (a Server Component) because
   * the env vars have no `NEXT_PUBLIC_` prefix and so are unreadable from the
   * client bundle. Server render and hydration both receive them as a prop, so
   * the two agree and the theme does not flash Rhesis blue first.
   */
  brandColors?: BrandColors;
}

const THEME_MODE_KEY = 'theme-mode';
/** Set once the mode comes from an explicit toggle, never cleared afterwards
 * — that's what tells the OS-preference listener below to stop following. */
const THEME_MODE_EXPLICIT_KEY = 'theme-mode-explicit';

/**
 * Writes the resolved mode to the cookie and localStorage regardless of how
 * it was determined. Previously this only ran from the toggle, so a visitor
 * who never touched the toggle (relying on `prefers-color-scheme` alone) had
 * no cookie — the server always guessed 'light' and every reload replayed the
 * light-render-then-flip-to-dark race on hydration. Persisting the
 * OS-detected mode too means only the very first visit ever needs the flip.
 */
function persistThemeMode(mode: 'light' | 'dark', explicit: boolean) {
  localStorage.setItem(THEME_MODE_KEY, mode);
  if (explicit) localStorage.setItem(THEME_MODE_EXPLICIT_KEY, '1');
  document.documentElement.setAttribute('data-theme-mode', mode);
  document.cookie = `${THEME_MODE_KEY}=${mode};path=/;max-age=31536000;SameSite=Lax`;
}

function resolveMode(): 'light' | 'dark' {
  const attr = document.documentElement.getAttribute('data-theme-mode');
  if (attr === 'light' || attr === 'dark') return attr;
  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

export default function ThemeContextProvider({
  children,
  disableTransitionOnChange = false,
  initialMode = 'light',
  brandColors,
}: ThemeContextProviderProps) {
  const [mode, setMode] = React.useState<'light' | 'dark'>(initialMode);

  React.useLayoutEffect(() => {
    const resolved = resolveMode();
    setMode(resolved);
    persistThemeMode(resolved, false);
  }, []);

  React.useEffect(() => {
    if (localStorage.getItem(THEME_MODE_EXPLICIT_KEY)) return;

    const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      const newMode = e.matches ? 'dark' : 'light';
      setMode(newMode);
      persistThemeMode(newMode, false);
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
          persistThemeMode(newMode, true);
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

  // Destructured so the memo keys on the colour values rather than the object's
  // identity — a fresh `{primary, secondary}` literal from the caller would
  // otherwise rebuild the whole theme on every render.
  const brandPrimary = brandColors?.primary;
  const brandSecondary = brandColors?.secondary;
  const theme = React.useMemo(
    () =>
      createTheme(
        getDesignTokens(mode, {
          primary: brandPrimary,
          secondary: brandSecondary,
        })
      ),
    [mode, brandPrimary, brandSecondary]
  );

  return (
    <ColorModeContext.Provider value={colorMode}>
      <MuiThemeProvider
        theme={theme}
        disableTransitionOnChange={disableTransitionOnChange}
      >
        {children}
      </MuiThemeProvider>
    </ColorModeContext.Provider>
  );
}
