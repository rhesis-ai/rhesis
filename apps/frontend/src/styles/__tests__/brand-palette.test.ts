import { getContrastRatio } from '@mui/system/colorManipulator';
import {
  contrastTextFor,
  deriveBrandAccents,
  deriveBrandPrimary,
  deriveBrandSecondary,
  deriveBrandSurfaces,
  deriveSecondaryAccents,
} from '../brand-palette';
import { getDesignTokens } from '../theme';

/** A dark brand colour, far enough from Rhesis blue to make swaps obvious. */
const BRAND = '#6A1B9A';
/** A pale brand colour, to prove contrast is computed and not assumed white. */
const PALE_BRAND = '#FDD803';

describe('contrastTextFor', () => {
  it('uses white on a dark brand colour', () => {
    expect(contrastTextFor(BRAND)).toBe('#FFFFFF');
  });

  it('uses near-black on a pale brand colour', () => {
    expect(contrastTextFor(PALE_BRAND)).toBe('#1A1A1A');
  });

  it('always clears the WCAG UI-component ratio', () => {
    for (const color of [BRAND, PALE_BRAND, '#808080', '#FFFFFF', '#000000']) {
      expect(
        getContrastRatio(color, contrastTextFor(color))
      ).toBeGreaterThanOrEqual(3);
    }
  });
});

describe('deriveBrandPrimary', () => {
  it('keeps the brand colour as light-mode main', () => {
    expect(deriveBrandPrimary(BRAND, 'light').main).toBe(BRAND);
  });

  it('lifts main and demotes the raw brand colour in dark mode', () => {
    const dark = deriveBrandPrimary(BRAND, 'dark');
    expect(dark.dark).toBe(BRAND);
    expect(dark.main).not.toBe(BRAND);
    // Lighter against a dark surface, matching how the Rhesis dark palette
    // promotes #33A6CB over #0080AF.
    expect(getContrastRatio(dark.main, '#0D1117')).toBeGreaterThan(
      getContrastRatio(BRAND, '#0D1117')
    );
  });

  it('reproduces the hand-picked Rhesis shades from #0080AF', () => {
    // The factors in brand-palette.ts were fitted to the Figma palette; if
    // someone retunes them, this is the check that says how far they drifted.
    const light = deriveBrandPrimary('#0080AF', 'light');
    // Designed #005F82 is rgb(0, 95, 130) — one unit per channel away.
    expect(light.dark).toBe('rgb(0, 94, 129)');
  });

  it('picks readable button text for a pale brand colour', () => {
    expect(deriveBrandPrimary(PALE_BRAND, 'light').contrastText).toBe(
      '#1A1A1A'
    );
  });
});

describe('deriveBrandSurfaces', () => {
  it('lands near the designed Rhesis tints for #0080AF', () => {
    const surfaces = deriveBrandSurfaces('#0080AF');
    // Designed #F2F9FD is rgb(242, 249, 253) and #E4F2FA is rgb(228, 242, 250);
    // the derived tints sit within a few units of both.
    expect(surfaces.light1).toBe('rgb(242, 248, 251)');
    expect(surfaces.light2).toBe('rgb(229, 242, 247)');
  });

  it('orders the tints from lightest to strongest', () => {
    const s = deriveBrandSurfaces(BRAND);
    const contrastOnWhite = (c: string) => getContrastRatio(c, '#FFFFFF');
    expect(contrastOnWhite(s.light1)).toBeLessThan(contrastOnWhite(s.light2));
    expect(contrastOnWhite(s.light2)).toBeLessThan(contrastOnWhite(s.light3));
    expect(contrastOnWhite(s.light3)).toBeLessThan(contrastOnWhite(s.light4));
  });
});

describe('deriveBrandAccents', () => {
  it('returns the Figma literals verbatim when no brand colour is set', () => {
    // These are the exact strings the component overrides used before the
    // brand hook existed, so the default theme is untouched.
    expect(deriveBrandAccents('light')).toEqual({
      main: '#0080AF',
      mainHover: '#005F82',
      contrastText: '#FFFFFF',
      onSurface: '#0080AF',
      softHover: 'rgba(0, 128, 175, 0.04)',
    });
    expect(deriveBrandAccents('dark').onSurface).toBe('#33A6CB');
  });

  it('uses the brand colour for solid fills in both modes', () => {
    expect(deriveBrandAccents('light', BRAND).main).toBe(BRAND);
    expect(deriveBrandAccents('dark', BRAND).main).toBe(BRAND);
  });

  it('lightens only the on-surface colour for dark mode', () => {
    expect(deriveBrandAccents('dark', BRAND).onSurface).not.toBe(BRAND);
    expect(deriveBrandAccents('light', BRAND).onSurface).toBe(BRAND);
  });
});

describe('deriveBrandSecondary', () => {
  it('builds a lighten/darken ramp around the configured colour', () => {
    const s = deriveBrandSecondary(BRAND);
    expect(s.main).toBe(BRAND);
    expect(s.light).not.toBe(s.main);
    expect(s.dark).not.toBe(s.main);
    expect(getContrastRatio(s.light, '#FFFFFF')).toBeLessThan(
      getContrastRatio(s.dark, '#FFFFFF')
    );
  });

  it('picks readable label text for a pale secondary', () => {
    expect(deriveBrandSecondary(PALE_BRAND).contrastText).toBe('#1A1A1A');
    expect(deriveBrandSecondary(BRAND).contrastText).toBe('#FFFFFF');
  });
});

describe('deriveSecondaryAccents', () => {
  it('returns the Figma literals verbatim when nothing is configured', () => {
    // Including the orange→yellow hover and its dark label, so the default
    // secondary button is untouched.
    expect(deriveSecondaryAccents()).toEqual({
      main: '#FD6E12',
      mainHover: '#FDD803',
      contrastText: '#FFFFFF',
      hoverContrastText: '#1A1A1A',
    });
  });

  it('brightens on hover, matching the Rhesis behaviour', () => {
    const a = deriveSecondaryAccents(BRAND);
    expect(getContrastRatio(a.mainHover, '#FFFFFF')).toBeLessThan(
      getContrastRatio(a.main, '#FFFFFF')
    );
  });

  it('recomputes the label colour for the lighter hover fill', () => {
    // A hover fill light enough to need dark text must not keep white text.
    const a = deriveSecondaryAccents(PALE_BRAND);
    expect(a.hoverContrastText).toBe('#1A1A1A');
  });
});

describe('getDesignTokens brand integration', () => {
  it('is byte-identical to the Rhesis palette when no brand colour is passed', () => {
    // The regression guard: adding the parameter must not shift the default look.
    for (const mode of ['light', 'dark'] as const) {
      const palette = getDesignTokens(mode).palette;
      expect(palette.primary).toEqual(
        mode === 'light'
          ? {
              main: '#0080AF',
              light: '#33A6CB',
              dark: '#005F82',
              contrastText: '#FFFFFF',
            }
          : {
              main: '#33A6CB',
              light: '#66C2DC',
              dark: '#0080AF',
              contrastText: '#FFFFFF',
            }
      );
      expect(palette.secondary).toEqual(
        mode === 'light'
          ? {
              main: '#FD6E12',
              light: '#FDD803',
              dark: '#1A1A1A',
              contrastText: '#FFFFFF',
            }
          : {
              main: '#FD6E12',
              light: '#F78166',
              dark: '#58A6FF',
              contrastText: '#FFFFFF',
            }
      );
      expect(palette.brandColor).toBeUndefined();
      expect(palette.brandSecondaryColor).toBeUndefined();
    }

    expect(getDesignTokens('light').palette.background).toMatchObject({
      light1: '#F2F9FD',
      light2: '#E4F2FA',
      light3: '#C2E5F5',
      light4: '#33A6CB',
    });
  });

  it('applies a brand colour to the palette and exposes the raw value', () => {
    const palette = getDesignTokens('light', { primary: BRAND }).palette;
    expect(palette.primary.main).toBe(BRAND);
    expect(palette.brandColor).toBe(BRAND);
    expect(palette.background.light4).not.toBe('#33A6CB');
  });

  it('lets either colour be set on its own', () => {
    // A deployment that only wants a new primary must not lose the Rhesis
    // secondary, and vice versa.
    const primaryOnly = getDesignTokens('light', { primary: BRAND }).palette;
    expect(primaryOnly.primary.main).toBe(BRAND);
    expect(primaryOnly.secondary.main).toBe('#FD6E12');

    const secondaryOnly = getDesignTokens('light', {
      secondary: PALE_BRAND,
    }).palette;
    expect(secondaryOnly.secondary.main).toBe(PALE_BRAND);
    expect(secondaryOnly.primary.main).toBe('#0080AF');
    expect(secondaryOnly.background.light1).toBe('#F2F9FD');
  });

  it('leaves dark-mode background tints as greys', () => {
    // Only light mode's light1-4 are brand-tinted; dark's are true greys.
    expect(
      getDesignTokens('dark', { primary: BRAND }).palette.background
    ).toMatchObject({
      light1: '#0D1117',
      light2: '#161B22',
    });
  });
});
