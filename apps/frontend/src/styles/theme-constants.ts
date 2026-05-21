/**
 * Design tokens that are safe to import from both server and client components.
 * Unlike theme.ts (which is 'use client'), this file has no client-side imports.
 */

export const GREYSCALE = {
  light: {
    title: '#1a1c20',
    body: '#2a2e36',
    label: '#545a65',
    subtitle: '#7f8a9b',
    border: '#cdd2da',
    surface1: '#f7f8f9',
    surface2: '#eef0f3',
    /** Figma Data Output Textfield fill (read-only ViewField) */
    fieldSurface: '#f9f9fa',
  },
  dark: {
    title: '#e6edf3',
    body: '#c9d1d9',
    label: '#8b949e',
    subtitle: '#8b949e',
    border: '#30363d',
    surface1: '#161b22',
    surface2: '#0d1117',
    /** Figma dark read-only field fill */
    fieldSurface: '#2a2e36',
  },
} as const;

export const BORDER_RADIUS = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  pill: '999px',
} as const;

export const BACKDROP_COLORS = {
  /** Teal overlay — used for create/edit entity drawers */
  create: 'rgba(0, 101, 140, 0.8)',
  /** Teal overlay — used for filter drawers (matches create) */
  filter: 'rgba(0, 101, 140, 0.8)',
} as const;

export const ELEVATION = {
  xs: '0px 2px 4px rgba(84, 90, 101, 0.25)',
  s: '0px 16px 32px -4px rgba(84, 90, 101, 0.10), 0px 4px 4px rgba(84, 90, 101, 0.04)',
  m: '0px 24px 48px -8px rgba(84, 90, 101, 0.12), 0px 4px 4px rgba(84, 90, 101, 0.04)',
  l: '0px 40px 80px -16px rgba(84, 90, 101, 0.18), 0px 4px 4px rgba(84, 90, 101, 0.04)',
  xl: '0px 56px 112px -20px rgba(0, 0, 0, 0.25), 0px 4px 4px rgba(84, 90, 101, 0.04)',
} as const;
