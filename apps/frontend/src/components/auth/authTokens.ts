/**
 * Design tokens for the auth pages.
 *
 * These mirror rhesis.ai rather than the app's own MUI theme: the sign-in
 * screen is the seam between the marketing site and the product, so it uses
 * the website's palette, type and shapes verbatim. Source of truth is
 * `website/src/styles/tailwind.css` plus `website/src/components/home/*`.
 *
 * Nothing outside `src/components/auth/` and `src/app/auth/` should import
 * this — the rest of the app stays on the MUI theme and Be Vietnam Pro.
 */

import { alpha, darken, lighten } from '@mui/system/colorManipulator';

/** Geist, registered in `src/styles/fonts.css`. Auth pages only. */
export const AUTH_FONT_SANS =
  '"Geist", "Be Vietnam Pro", system-ui, sans-serif';
/** Geist Mono — the badge row under the message column. */
export const AUTH_FONT_MONO = '"Geist Mono", "Sometype Mono", monospace';
/** Sora stays the wordmark face, matching the website navbar. */
export const AUTH_FONT_DISPLAY = '"Sora", "Be Vietnam Pro", sans-serif';

/**
 * Returns the sans-serif font stack with a brand font prepended when one is
 * configured. The brand font replaces Geist as the primary face, with Geist
 * and Be Vietnam Pro as fallbacks.
 */
export function authFontSans(brandFontFamily?: string): string {
  return brandFontFamily
    ? `"${brandFontFamily}", ${AUTH_FONT_SANS}`
    : AUTH_FONT_SANS;
}

/** Display stack with brand font prepended when configured. */
export function authFontDisplay(brandFontFamily?: string): string {
  return brandFontFamily
    ? `"${brandFontFamily}", ${AUTH_FONT_DISPLAY}`
    : AUTH_FONT_DISPLAY;
}

export interface AuthTokens {
  /** Page background behind the wash/aurora. */
  ground: string;
  /** Auth card fill. */
  surface: string;
  /** Headings and input text. */
  ink: string;
  /** Body copy. */
  body: string;
  /** Secondary copy, nav links, helper text. */
  muted: string;
  /** Borders, dividers, badge outlines. */
  hairline: string;
  /** Buttons, links, the accent words in the headline. */
  accent: string;
  accentHover: string;
  /** Text field fill. */
  field: string;
  fieldBorder: string;
  /** Eyebrow pill fill. */
  pill: string;
  /** Badge fill in the fact row. */
  badge: string;
  /** GitHub chip in the nav. */
  chip: string;
  cardShadow: string;
  /** Glow under the primary button. */
  accentShadow: string;
}

const LIGHT: AuthTokens = {
  ground: '#f9fafa',
  surface: '#ffffff',
  ink: '#000000',
  body: '#2c2c2c',
  muted: '#4b5563',
  hairline: '#dde3e3',
  accent: '#0080af',
  accentHover: '#006d96',
  field: '#ffffff',
  fieldBorder: '#dde3e3',
  pill: '#ffffff',
  badge: 'rgba(255,255,255,0.6)',
  chip: '#f3f4f6',
  cardShadow: '0 1px 3px rgba(0,0,0,0.06), 0 18px 40px -14px rgba(0,0,0,0.16)',
  accentShadow: '0 6px 14px -4px rgba(0,128,175,0.55)',
};

/**
 * The website keeps `#0080af` on dark, which sits at roughly 4.3:1 against
 * `#030712` — legible, but the buttons carry white text on top of it. Lifting
 * the accent to `#22a5d1` keeps both the accent words and the button label
 * comfortably above 4.5:1 without leaving the brand's blue.
 */
const DARK: AuthTokens = {
  ground: '#030712',
  surface: 'rgba(255,255,255,0.045)',
  ink: '#ffffff',
  body: '#d1d5db',
  muted: '#9ca3af',
  hairline: 'rgba(255,255,255,0.14)',
  accent: '#22a5d1',
  accentHover: '#41b6dd',
  field: 'rgba(255,255,255,0.04)',
  fieldBorder: 'rgba(255,255,255,0.16)',
  pill: 'rgba(255,255,255,0.1)',
  badge: 'transparent',
  chip: 'rgba(255,255,255,0.08)',
  cardShadow: '0 1px 3px rgba(0,0,0,0.4), 0 18px 40px -14px rgba(0,0,0,0.6)',
  accentShadow: '0 6px 14px -4px rgba(34,165,209,0.4)',
};

/**
 * Applies a deployment's `BRAND_PRIMARY_COLOR` to the three accent tokens.
 *
 * The sign-in screen is the first thing a white-label user sees, so leaving it
 * on Rhesis blue while the app itself is rebranded is the most visible way to
 * get this wrong. The dark-mode lift mirrors what the hand-picked pair already
 * does (`#0080af` → `#22a5d1`, i.e. roughly `lighten(0.13)`) — a saturated
 * brand colour carrying white button text needs the extra contrast against
 * `#030712`.
 */
function withBrandAccent(tokens: AuthTokens, brandColor: string): AuthTokens {
  const accent =
    tokens === DARK ? lighten(brandColor, 0.13) : brandColor.toLowerCase();

  return {
    ...tokens,
    accent,
    accentHover: tokens === DARK ? lighten(accent, 0.15) : darken(accent, 0.15),
    accentShadow: `0 6px 14px -4px ${alpha(accent, tokens === DARK ? 0.4 : 0.55)}`,
  };
}

export function getAuthTokens(
  mode: 'light' | 'dark',
  brandColor?: string
): AuthTokens {
  const tokens = mode === 'dark' ? DARK : LIGHT;
  return brandColor ? withBrandAccent(tokens, brandColor) : tokens;
}

/** Shapes, lifted from the website's radius scale and hero CTAs. */
export const AUTH_SHAPE = {
  /** Full pill — every button on the page. */
  button: '9999px',
  buttonHeight: 48,
  /** `--radius-2xl`. */
  card: '16px',
  /** `--radius-md`, the hero eyebrow pill. */
  pill: '6px',
  input: '10px',
} as const;
