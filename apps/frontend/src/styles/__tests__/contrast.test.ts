import { blend, getContrastRatio } from '@mui/system/colorManipulator';
import { createTheme, type PaletteMode } from '@mui/material/styles';
import {
  ensureContrastOnAll,
  fillUnderText,
  textOnFill,
  TEXT_CONTRAST,
  UI_CONTRAST,
} from '../contrast';
import { getDesignTokens } from '../theme';
import { BACKGROUND_DEFAULT } from '../theme-background';

const MODES: PaletteMode[] = ['light', 'dark'];

// Defaults plus brand colours an org might pick: pale, mid-grey, saturated, dark.
const BRANDS: Array<{ primary?: string; secondary?: string }> = [
  {},
  { primary: '#FDD803', secondary: '#B3E5FC' },
  { primary: '#808080', secondary: '#9E9E9E' },
  { primary: '#E91E63', secondary: '#00C853' },
  { primary: '#0D1B2A', secondary: '#3E2723' },
];

const SURFACES: Record<PaletteMode, string[]> = {
  light: [
    '#FFFFFF',
    BACKGROUND_DEFAULT.light,
    getDesignTokens('light').palette.greyscale.surface1,
  ],
  dark: [
    '#161B22',
    BACKGROUND_DEFAULT.dark,
    getDesignTokens('dark').palette.greyscale.fieldSurface,
  ],
};

const minRatio = (color: string, backgrounds: string[]) =>
  Math.min(...backgrounds.map(bg => getContrastRatio(color, bg)));

describe('ensureContrastOnAll', () => {
  it('leaves a colour that already passes untouched', () => {
    expect(
      ensureContrastOnAll('#1A1A1A', ['#FFFFFF'], TEXT_CONTRAST, 'light')
    ).toBe('#1A1A1A');
  });

  it('reaches the ratio for any starting colour, even white on white', () => {
    const result = ensureContrastOnAll(
      '#FFFFFF',
      ['#FFFFFF'],
      TEXT_CONTRAST,
      'light'
    );
    expect(getContrastRatio(result, '#FFFFFF')).toBeGreaterThanOrEqual(
      TEXT_CONTRAST
    );
  });
});

describe('textOnFill', () => {
  it.each(['#FFFFFF', '#000000', '#808080', '#0080AF', '#FDD803'])(
    'finds a 4.5:1 label for %s',
    fill => {
      expect(getContrastRatio(textOnFill(fill), fill)).toBeGreaterThanOrEqual(
        TEXT_CONTRAST
      );
    }
  );
});

describe('fillUnderText', () => {
  it('darkens a hover fill under a white label', () => {
    const fill = fillUnderText('#33A6CB', '#FFFFFF');
    expect(getContrastRatio('#FFFFFF', fill)).toBeGreaterThanOrEqual(
      TEXT_CONTRAST
    );
  });
});

describe('accessible colours mode', () => {
  describe.each(MODES)('%s mode', mode => {
    it.each(BRANDS.map(brand => [JSON.stringify(brand), brand]))(
      'keeps text and controls at AA for brand %s',
      (_label, brand) => {
        const { palette } = createTheme(
          getDesignTokens(mode, { ...brand, accessibleColors: true })
        );
        const surfaces = SURFACES[mode];

        for (const key of [
          'primary',
          'secondary',
          'success',
          'warning',
          'error',
          'info',
        ] as const) {
          const color = palette[key];
          // `main` is used as text on the page and on its own 12% tint...
          const tint = blend(surfaces[0], color.main, 0.12);
          expect(
            minRatio(color.main, [...surfaces, tint])
          ).toBeGreaterThanOrEqual(TEXT_CONTRAST);
          // ...and as a filled background under its label.
          expect(
            getContrastRatio(color.contrastText, color.main)
          ).toBeGreaterThanOrEqual(TEXT_CONTRAST);
        }

        expect(
          minRatio(palette.greyscale.label, surfaces)
        ).toBeGreaterThanOrEqual(TEXT_CONTRAST);
        expect(
          minRatio(palette.greyscale.subtitle, surfaces)
        ).toBeGreaterThanOrEqual(TEXT_CONTRAST);
        expect(
          minRatio(palette.text.disabled, surfaces)
        ).toBeGreaterThanOrEqual(TEXT_CONTRAST);
      }
    );

    it('gives input borders 3:1', () => {
      const tokens = getDesignTokens(mode, { accessibleColors: true });
      const border = tokens.components.MuiOutlinedInput.styleOverrides
        .notchedOutline.borderColor as string;
      expect(minRatio(border, SURFACES[mode])).toBeGreaterThanOrEqual(
        UI_CONTRAST
      );
    });
  });

  it('changes nothing when off', () => {
    for (const mode of MODES) {
      expect(getDesignTokens(mode, { accessibleColors: false })).toEqual(
        getDesignTokens(mode)
      );
    }
    const light = getDesignTokens('light');
    expect(light.palette.primary?.main).toBe('#0080AF');
    expect(light.palette.greyscale.subtitle).toBe('#7f8a9b');
  });
});
