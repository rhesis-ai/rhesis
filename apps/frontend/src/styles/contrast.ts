/**
 * Contrast helpers for the "accessible colours" theme mode.
 *
 * When an organisation turns the mode on, every colour the theme draws text or
 * component boundaries with is nudged — keeping its hue — until it meets WCAG
 * 2.1 AA against the surfaces it sits on: 4.5:1 for text (1.4.3), 3:1 for
 * borders, icons and focus indicators (1.4.11). That holds for the Rhesis
 * defaults and for any brand colour an organisation configures, so branding
 * choices can't break the guarantee.
 */
import { blend, getContrastRatio } from '@mui/system/colorManipulator';
import { ensureContrast } from './brand-palette';

export const TEXT_CONTRAST = 4.5;
export const UI_CONTRAST = 3;

/** Opacity of the self-tinted chip/badge backgrounds used across the app. */
const CHIP_TINT = 0.12;
const MAX_PASSES = 10;
/**
 * Aim a little above each threshold: checkers such as axe measure the rendered
 * colour and can land a hair below a value that passes exactly here.
 */
const HEADROOM = 0.1;

/** Text candidates for a filled background, in order of preference. */
const TEXT_ON_FILL = ['#FFFFFF', '#1A1A1A', '#000000'];

function minRatio(color: string, backgrounds: readonly string[]): number {
  return Math.min(...backgrounds.map(bg => getContrastRatio(color, bg)));
}

/**
 * `ensureContrast` from brand-palette, against several backgrounds at once: it
 * keeps lifting against the worst one until all pass. Colours that already pass
 * are returned unchanged. `backgrounds` may depend on the colour itself (a tint
 * of it), so it is re-evaluated each pass.
 */
export function ensureContrastOnAll(
  color: string,
  backgrounds: readonly string[] | ((current: string) => string[]),
  ratio: number,
  mode: 'light' | 'dark'
): string {
  const against = (c: string) =>
    typeof backgrounds === 'function' ? backgrounds(c) : backgrounds;
  const target = ratio + HEADROOM;
  let current = color;
  for (let i = 0; i < MAX_PASSES; i++) {
    const bgs = against(current);
    if (minRatio(current, bgs) >= target) return current;
    const worst = bgs.reduce((a, b) =>
      getContrastRatio(current, a) <= getContrastRatio(current, b) ? a : b
    );
    current = ensureContrast(current, worst, target);
  }
  if (minRatio(current, against(current)) >= target) return current;
  // The guarantee matters more than the hue.
  return mode === 'light' ? '#000000' : '#FFFFFF';
}

/** The most preferred text colour that reaches 4.5:1 on `fill`, else the best one. */
export function textOnFill(fill: string): string {
  const passing = TEXT_ON_FILL.find(
    text => getContrastRatio(text, fill) >= TEXT_CONTRAST + HEADROOM
  );
  if (passing) return passing;
  return TEXT_ON_FILL.reduce((best, text) =>
    getContrastRatio(text, fill) > getContrastRatio(best, fill) ? text : best
  );
}

/**
 * Moves a fill away from a fixed label colour until the label reaches 4.5:1:
 * darker under a light label, lighter under a dark one. For hover fills, whose
 * label is inherited from the resting state.
 */
export function fillUnderText(fill: string, label: string): string {
  const labelIsLight = getContrastRatio(label, '#000000') > 10;
  return ensureContrastOnAll(
    fill,
    [label],
    TEXT_CONTRAST,
    labelIsLight ? 'light' : 'dark'
  );
}

export interface PaletteColorLike {
  main: string;
  light?: string;
  dark?: string;
  contrastText?: string;
}

export interface AccessibleColors {
  /** Colour used as text on the mode's surfaces. */
  text: (color: string) => string;
  /** Colour used for borders, icons and other non-text UI on the surfaces. */
  ui: (color: string) => string;
  /** Text on a tinted background (e.g. a chip) that must also pass on the page. */
  textOn: (color: string, background: string) => string;
  /** A palette colour whose `main` is used as text and as a labelled fill. */
  paletteColor: <T extends PaletteColorLike>(color: T) => T;
}

export function accessibleColors(
  mode: 'light' | 'dark',
  surfaces: readonly string[]
): AccessibleColors {
  const text = (color: string) =>
    ensureContrastOnAll(color, surfaces, TEXT_CONTRAST, mode);
  return {
    text,
    ui: color => ensureContrastOnAll(color, surfaces, UI_CONTRAST, mode),
    textOn: (color, background) =>
      ensureContrastOnAll(
        color,
        [background, ...surfaces],
        TEXT_CONTRAST,
        mode
      ),
    paletteColor: color => {
      // Chips and badges put `main` text on a tint of itself
      // (`alpha(main, 0.12)`), which is lighter/darker than any page surface.
      const main = ensureContrastOnAll(
        color.main,
        current => [...surfaces, blend(surfaces[0], current, CHIP_TINT)],
        TEXT_CONTRAST,
        mode
      );
      const contrastText = textOnFill(main);
      return {
        ...color,
        main,
        contrastText,
        // MUI uses `dark` as the contained-button hover fill under the same label.
        ...(color.dark && { dark: fillUnderText(color.dark, contrastText) }),
      };
    },
  };
}
