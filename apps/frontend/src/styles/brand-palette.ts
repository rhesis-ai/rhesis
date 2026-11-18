/**
 * Derives a primary palette from a single configured brand colour, for
 * deployments that set `BRAND_PRIMARY_COLOR` (see `config/branding.ts`).
 *
 * The lighten/darken factors here are not arbitrary — they are the ones that
 * reproduce the hand-picked Rhesis palette from `#0080AF` almost exactly
 * (`darken(0.26)` lands on `#005F82`, `lighten(0.95)` on `#F2F8FB` against a
 * designed `#F2F9FD`). So a custom colour gets the same relationships the
 * Figma palette was built with, rather than a fresh guess.
 *
 * Imports the colour helpers from `@mui/system/colorManipulator` rather than
 * `@mui/material/styles`: they are pure functions, and the deep path keeps this
 * module importable from server components too.
 */
import {
  alpha,
  darken,
  decomposeColor,
  getContrastRatio,
  getLuminance,
  hslToRgb,
  lighten,
  rgbToHex,
} from '@mui/system/colorManipulator';
import { BACKGROUND_PAPER } from '@/styles/theme-background';

/** The Rhesis primary. Also the reference point the factors below were fitted to. */
const RHESIS_PRIMARY = '#0080AF';

/** Dark text for light brand colours — matches `text.secondary` in the theme. */
const DARK_CONTRAST_TEXT = '#1A1A1A';
const LIGHT_CONTRAST_TEXT = '#FFFFFF';

/** MUI's own default `contrastThreshold`, i.e. the WCAG ratio for UI components
 * and large text. Buttons and chips are the main consumers. */
const CONTRAST_THRESHOLD = 3;

/**
 * How far a brand colour used as text or an outline must stand out from the
 * surface it sits on, per mode.
 *
 * Light mode asks for WCAG's 3:1 (UI components and large text): darkening a
 * brand colour drags it toward black fast, and 4.5:1 would already shift
 * mid-tones like Rhesis blue itself. Dark mode asks for WCAG's 4.5:1 (body
 * text) because lifting is cheap there.
 */
const MIN_ACCENT_CONTRAST: Record<'light' | 'dark', number> = {
  light: 3,
  dark: 4.5,
};

/** A solid fill carries its own label, so it only needs to read as a shape. */
const MIN_FILL_CONTRAST = 3;

function toHsl(color: string): [number, number, number] {
  const [r, g, b] = decomposeColor(color).values.map(v => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  if (d === 0) return [0, 0, l];
  const s = d / (1 - Math.abs(2 * l - 1));
  const h =
    max === r
      ? ((g - b) / d) % 6
      : max === g
        ? (b - r) / d + 2
        : (r - g) / d + 4;
  return [(h * 60 + 360) % 360, s, l];
}

/**
 * Returns `color` unchanged if it already reaches `minRatio` against
 * `background`; otherwise the closest HSL lightness, raised on a dark
 * background or lowered on a light one, that does.
 *
 * Moves lightness rather than mixing with white/black (MUI's `lighten`), which
 * greys a colour out: a lifted navy stays a recognisable blue instead of slate.
 */
export function ensureContrast(
  color: string,
  background: string,
  minRatio: number
): string {
  if (getContrastRatio(color, background) >= minRatio) return color;

  const [h, s, l] = toHsl(color);
  const at = (lightness: number) =>
    rgbToHex(hslToRgb(`hsl(${h}, ${s * 100}%, ${lightness * 100}%)`));
  const onDark = getLuminance(background) < 0.5;
  // Binary search between the colour and white (or black), keeping the passing end.
  let near = l;
  let far = onDark ? 1 : 0;
  for (let i = 0; i < 16; i++) {
    const mid = (near + far) / 2;
    if (getContrastRatio(at(mid), background) >= minRatio) far = mid;
    else near = mid;
  }
  return at(far);
}

export interface BrandPrimary {
  main: string;
  light: string;
  dark: string;
  contrastText: string;
}

export interface BrandSurfaces {
  light1: string;
  light2: string;
  light3: string;
  light4: string;
}

/**
 * Picks white or near-black text for a background, so a pale brand colour
 * (yellow, mint) still gets readable button labels instead of white-on-white.
 */
export function contrastTextFor(background: string): string {
  return getContrastRatio(background, LIGHT_CONTRAST_TEXT) >= CONTRAST_THRESHOLD
    ? LIGHT_CONTRAST_TEXT
    : DARK_CONTRAST_TEXT;
}

/**
 * Builds `palette.primary` for one mode.
 *
 * `main` is the brand colour moved only as far as it must be to read on the
 * mode's paper, so a dark navy is lifted on dark and a pale yellow darkened on
 * light, while a colour that already reads stays exact.
 */
export function deriveBrandPrimary(
  brandColor: string,
  mode: 'light' | 'dark'
): BrandPrimary {
  const main = ensureContrast(
    brandColor,
    BACKGROUND_PAPER[mode],
    MIN_ACCENT_CONTRAST[mode]
  );

  return {
    main,
    light: lighten(brandColor, mode === 'light' ? 0.25 : 0.45),
    dark: mode === 'light' ? darken(brandColor, 0.26) : brandColor,
    contrastText: contrastTextFor(main),
  };
}

/**
 * Builds the light-mode `background.light1`–`light4` tints.
 *
 * These four are brand-tinted surfaces, not greys — 12 components read them for
 * hovers, selected rows and callouts. Leaving them at the Rhesis blues would
 * put a custom-coloured button on a blue panel, which reads as a half-finished
 * rebrand. Dark mode's equivalents are true greys and stay untouched.
 */
export function deriveBrandSurfaces(brandColor: string): BrandSurfaces {
  return {
    light1: lighten(brandColor, 0.95),
    light2: lighten(brandColor, 0.9),
    light3: lighten(brandColor, 0.75),
    light4: lighten(brandColor, 0.25),
  };
}

/**
 * Builds `palette.secondary` for one mode from a configured secondary colour.
 *
 * Unlike primary, the Rhesis secondary slots are not a tint ramp — `light` is
 * the accent yellow, and `dark` is near-black in light mode and a stray blue in
 * dark mode. There is no relationship to generalise, so a configured colour gets
 * a plain lighten/darken ramp instead. The defaults are kept verbatim when
 * nothing is configured, so this only applies to deployments that opt in.
 *
 * `main` is the same in both modes, matching the current theme, where the
 * secondary orange does not shift for dark surfaces the way primary does.
 */
export function deriveBrandSecondary(secondaryColor: string): BrandPrimary {
  return {
    main: secondaryColor,
    light: lighten(secondaryColor, 0.25),
    dark: darken(secondaryColor, 0.26),
    contrastText: contrastTextFor(secondaryColor),
  };
}

export interface SecondaryAccents {
  main: string;
  /** Hover fill. Brightens rather than darkens, keeping the spirit of the
   * Rhesis orange→yellow hover. */
  mainHover: string;
  contrastText: string;
  /** Text colour on top of `mainHover`, recomputed because a lighter fill can
   * flip the readable choice. */
  hoverContrastText: string;
}

/**
 * Resolves the secondary colours used directly by the contained/outlined
 * secondary button overrides. With no configured colour it returns the Figma
 * literals, including the orange→yellow hover and its dark label.
 */
export function deriveSecondaryAccents(
  secondaryColor?: string
): SecondaryAccents {
  if (!secondaryColor) {
    return {
      main: '#FD6E12',
      mainHover: '#FDD803',
      contrastText: '#FFFFFF',
      hoverContrastText: '#1A1A1A',
    };
  }

  const mainHover = lighten(secondaryColor, 0.25);
  return {
    main: secondaryColor,
    mainHover,
    contrastText: contrastTextFor(secondaryColor),
    hoverContrastText: contrastTextFor(mainHover),
  };
}

export interface BrandAccents {
  /** Solid brand fill: app bar, contained primary button, active pill. */
  main: string;
  /** Hover state for a solid brand fill. */
  mainHover: string;
  /** Text/icon colour placed on top of `main`. */
  contrastText: string;
  /** Brand colour readable *against* the current mode's surface — used for
   * outlined/text buttons, checkboxes and focus borders. */
  onSurface: string;
  /** Barely-there wash for text-button hover. */
  softHover: string;
}

/**
 * Resolves the brand-dependent colours that the `components` style overrides
 * use directly instead of going through `palette.primary`.
 *
 * Without this, a deployment's custom colour would reach buttons via the
 * palette but leave the app bar, checkboxes, pill toggles and input focus
 * borders on Rhesis blue. Passing no `brandColor` returns the exact Figma
 * literals those overrides were written with — including `softHover`, where
 * `alpha(#0080AF, 0.04)` reproduces the original `rgba(0, 128, 175, 0.04)`
 * string character for character.
 *
 * Chart palettes are deliberately not derived: a readable series palette needs
 * distinguishable hues, not tints of one colour.
 */
export function deriveBrandAccents(
  mode: 'light' | 'dark',
  brandColor?: string
): BrandAccents {
  if (!brandColor) {
    return {
      main: RHESIS_PRIMARY,
      mainHover: '#005F82',
      contrastText: contrastTextFor(RHESIS_PRIMARY),
      onSurface: mode === 'light' ? RHESIS_PRIMARY : '#33A6CB',
      softHover: alpha(RHESIS_PRIMARY, 0.04),
    };
  }

  const surface = BACKGROUND_PAPER[mode];
  const main = ensureContrast(brandColor, surface, MIN_FILL_CONTRAST);
  const onSurface = ensureContrast(
    brandColor,
    surface,
    MIN_ACCENT_CONTRAST[mode]
  );

  return {
    main,
    mainHover: darken(main, 0.26),
    contrastText: contrastTextFor(main),
    onSurface,
    softHover: alpha(main, 0.04),
  };
}
