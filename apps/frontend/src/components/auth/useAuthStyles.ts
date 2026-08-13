'use client';

import { useMemo } from 'react';
import { useTheme, type SxProps, type Theme } from '@mui/material/styles';
import {
  AUTH_FONT_SANS,
  AUTH_SHAPE,
  getAuthTokens,
  type AuthTokens,
} from './authTokens';

export interface AuthStyles {
  /** Resolved palette for the current mode — for one-off colours. */
  tokens: AuthTokens;
  /** Card title, e.g. "Sign in" / "Set a new password". */
  heading: SxProps<Theme>;
  /** The line under a card title. */
  subheading: SxProps<Theme>;
  /** Filled pill button — the primary action on every auth card. */
  primaryButton: SxProps<Theme>;
  /** Outlined pill button — OAuth providers, "Create an account". */
  outlinedButton: SxProps<Theme>;
  /** Text field, themed for both modes. */
  field: SxProps<Theme>;
  /** Small muted inline links ("Forgot password?"). */
  quietLink: SxProps<Theme>;
  /** Body copy inside a card. */
  body: SxProps<Theme>;
}

/**
 * Shared styling for everything rendered inside `AuthPageShell`.
 *
 * Auth pages don't use the app's MUI theme colours — they mirror rhesis.ai via
 * `authTokens`. Without this hook each page grows its own copy of the button
 * and field styling, which is exactly how the previous brand's accent and
 * hover pair ended up duplicated across five files.
 */
export function useAuthStyles(): AuthStyles {
  const { mode, brandColor } = useTheme().palette;

  return useMemo(() => {
    const t = getAuthTokens(mode, brandColor);

    return {
      tokens: t,
      heading: {
        fontFamily: AUTH_FONT_SANS,
        fontSize: 24,
        fontWeight: 700,
        letterSpacing: '-0.02em',
        color: t.ink,
      },
      subheading: {
        fontFamily: AUTH_FONT_SANS,
        fontSize: 14,
        color: t.muted,
      },
      body: {
        fontFamily: AUTH_FONT_SANS,
        fontSize: 14,
        lineHeight: 1.55,
        color: t.body,
      },
      primaryButton: {
        height: AUTH_SHAPE.buttonHeight,
        borderRadius: AUTH_SHAPE.button,
        fontFamily: AUTH_FONT_SANS,
        fontSize: 15,
        fontWeight: 700,
        textTransform: 'none',
        bgcolor: t.accent,
        color: '#fff',
        boxShadow: t.accentShadow,
        '&:hover': { bgcolor: t.accentHover, boxShadow: t.accentShadow },
      },
      outlinedButton: {
        height: AUTH_SHAPE.buttonHeight,
        borderRadius: AUTH_SHAPE.button,
        fontFamily: AUTH_FONT_SANS,
        fontSize: 15,
        fontWeight: 600,
        textTransform: 'none',
        color: t.ink,
        borderColor: t.hairline,
        borderWidth: '1.5px',
        '&:hover': {
          borderColor: t.accent,
          borderWidth: '1.5px',
          bgcolor: 'transparent',
        },
      },
      field: {
        '& .MuiOutlinedInput-root': {
          borderRadius: AUTH_SHAPE.input,
          bgcolor: t.field,
          fontFamily: AUTH_FONT_SANS,
          color: t.ink,
          '& fieldset': { borderColor: t.fieldBorder },
          '&:hover fieldset': { borderColor: t.muted },
          '&.Mui-focused fieldset': {
            borderColor: t.accent,
            borderWidth: '1.5px',
          },
        },
        '& .MuiInputLabel-root': {
          fontFamily: AUTH_FONT_SANS,
          color: t.muted,
          '&.Mui-focused': { color: t.accent },
        },
        '& .MuiFormHelperText-root': { color: t.muted },
      },
      quietLink: {
        fontFamily: AUTH_FONT_SANS,
        fontSize: 13,
        color: t.muted,
        textDecoration: 'none',
      },
    };
  }, [mode, brandColor]);
}
