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

/**
 * Plan colours, per mode: the crown for a paid plan, and its drop shadow.
 *
 * Deliberately **not** `warning.main`. Warning means "something needs your
 * attention", and a healthy paid plan is the opposite of that; reusing the
 * semantic role would also spend it, leaving nothing for real warning states in
 * the sidebar (which already has quota warnings). Two shades because the
 * light-mode gold has to survive a white surface while the dark one does not.
 *
 * **Why not a brighter, more obviously metallic gold in light mode.** The
 * classic `#D4AF37` is only 2.10:1 on white, well under the 3:1 WCAG 1.4.11
 * asks for a non-text graphic, and every gold at that lightness fails the same
 * way. `#B8860B` is the most saturated gold that clears the bar: hue 43°
 * (gold) rather than the 36° of an orange-brown, at 3.25:1. Dark mode has the
 * headroom for a bright `#F2C14E` at 10.31:1.
 *
 * Contrast against the sidebar background (white light / `#161B22` dark), per
 * WCAG 1.4.11 for non-text graphics (3:1): light 3.25:1, dark 10.31:1.
 *
 * The two shadow tokens are a pair: a tight, darker contact shadow plus a wider
 * halo. One alone is invisible at this size -- a single 2px gold shadow under a
 * gold glyph on a white card cannot be seen. In light mode the contact shadow is
 * a darker gold so it registers against white; in dark mode it is black, since
 * gold-on-dark needs the halo to read rather than a same-hue shadow.
 *
 * Values live here, in the token definition file, for the same reason
 * `GREYSCALE` does -- this is the one place a palette literal belongs.
 */
export const PLAN_COLORS = {
  light: {
    /** Crown for an active paid plan. */
    premium: '#B8860B',
  },
  dark: {
    premium: '#F2C14E',
  },
} as const;

/**
 * The paid crown's `filter`, complete, per mode.
 *
 * A whole value rather than colours the component assembles, matching how
 * `SHADOWS` below keeps entire `box-shadow` strings here: the offsets and blur
 * are as much of the design decision as the colour, and splitting them left
 * `0 1px 1.5px` and `0 0 5px` sitting in a component.
 *
 * Two chained shadows on purpose. A single pass at 24px is either invisible
 * (small blur) or a smudge (large blur), and one 2px gold shadow under a gold
 * glyph on a white card genuinely cannot be seen -- measured at 336 changed
 * pixels and a 89/255 peak delta, against 750 and 168/255 for the pair below.
 * The contact shadow seats the crown on the surface; the halo makes it glow.
 *
 * Light mode's contact shadow is a *darker* gold so it registers against white.
 * Dark mode's is black, because a same-hue shadow on a dark surface disappears
 * and the halo has to carry the effect.
 */
export const PLAN_CROWN_SHADOW = {
  light:
    'drop-shadow(0 1px 1.5px rgba(146, 105, 8, 0.70)) ' +
    'drop-shadow(0 0 5px rgba(184, 134, 11, 0.45))',
  dark:
    'drop-shadow(0 1px 1.5px rgba(0, 0, 0, 0.55)) ' +
    'drop-shadow(0 0 5px rgba(242, 193, 78, 0.45))',
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

/** Font size for monospace / code blocks (px). */
export const CODE_FONT_SIZE = 13;

/** Horizontal gap between FAB buttons in a page-header action group (Figma) */
export const FAB_GROUP_GAP = '20px';

/** Diameter of a page-header FAB (Figma). Shared by `Fab` and its skeleton. */
export const FAB_SIZE = 56;

/**
 * Inset for everything inside a grid card: the toolbar, the first and last
 * column, and the pagination footer (Figma). BaseDataGrid expresses the same
 * value as `theme.spacing(3.75)`.
 */
export const GRID_CARD_INSET = '30px';

/** Minimum height of a grid-card toolbar row (Figma). */
export const GRID_TOOLBAR_MIN_HEIGHT = 52;

/** MUI spacing units for section-level Grid containers (EditableSection, SectionCard). */
export const SECTION_GRID = {
  columnSpacing: 4,
  rowSpacing: 4,
} as const;

/** MUI spacing units for page-level section stacking. */
export const PAGE_SECTION_GAP = 3;

export const ELEVATION = {
  xs: '0px 2px 4px rgba(84, 90, 101, 0.25)',
  s: '0px 16px 32px -4px rgba(84, 90, 101, 0.10), 0px 4px 4px rgba(84, 90, 101, 0.04)',
  m: '0px 24px 48px -8px rgba(84, 90, 101, 0.12), 0px 4px 4px rgba(84, 90, 101, 0.04)',
  l: '0px 40px 80px -16px rgba(84, 90, 101, 0.18), 0px 4px 4px rgba(84, 90, 101, 0.04)',
  xl: '0px 56px 112px -20px rgba(0, 0, 0, 0.25), 0px 4px 4px rgba(84, 90, 101, 0.04)',
} as const;
