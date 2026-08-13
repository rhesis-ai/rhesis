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
  getContrastRatio,
  lighten,
} from '@mui/system/colorManipulator';

/** The Rhesis primary. Also the reference point the factors below were fitted to. */
const RHESIS_PRIMARY = '#0080AF';

/** Dark text for light brand colours — matches `text.secondary` in the theme. */
const DARK_CONTRAST_TEXT = '#1A1A1A';
const LIGHT_CONTRAST_TEXT = '#FFFFFF';

/** MUI's own default `contrastThreshold`, i.e. the WCAG ratio for UI components
 * and large text. Buttons and chips are the main consumers. */
const CONTRAST_THRESHOLD = 3;

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
 * Dark mode shifts `main` lighter and keeps the raw brand colour as `dark`,
 * mirroring how the Rhesis dark palette promotes `#33A6CB` to `main` and
 * demotes `#0080AF` — a saturated brand colour is hard to read on a dark
 * surface at full strength.
 */
export function deriveBrandPrimary(
  brandColor: string,
  mode: 'light' | 'dark'
): BrandPrimary {
  const main = mode === 'light' ? brandColor : lighten(brandColor, 0.25);

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
  const main = brandColor ?? RHESIS_PRIMARY;

  return {
    main,
    mainHover: brandColor ? darken(brandColor, 0.26) : '#005F82',
    contrastText: contrastTextFor(main),
    onSurface:
      mode === 'light'
        ? main
        : brandColor
          ? lighten(brandColor, 0.25)
          : '#33A6CB',
    softHover: alpha(main, 0.04),
  };
}
