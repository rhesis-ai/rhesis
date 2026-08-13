import { getContrastRatio } from '@mui/system/colorManipulator';
import { getAuthTokens } from '../authTokens';

/** netgo green — the colour that motivated the branding feature. */
const BRAND = '#005B33';

describe('getAuthTokens', () => {
  it('keeps the rhesis.ai accents when no brand colour is configured', () => {
    expect(getAuthTokens('light').accent).toBe('#0080af');
    expect(getAuthTokens('dark').accent).toBe('#22a5d1');
    expect(getAuthTokens('light').accentShadow).toBe(
      '0 6px 14px -4px rgba(0,128,175,0.55)'
    );
  });

  it('applies a configured brand colour to the accents', () => {
    const light = getAuthTokens('light', BRAND);
    expect(light.accent).toBe('#005b33');
    expect(light.accentHover).not.toBe(light.accent);
    expect(light.accentShadow).toContain('rgba(0, 91, 51, 0.55)');
  });

  it('leaves the non-accent tokens alone', () => {
    // Only the three accent tokens are brand-driven; ground, ink and the
    // hairlines mirror the website and stay put.
    const plain = getAuthTokens('dark');
    const branded = getAuthTokens('dark', BRAND);
    expect(branded.ground).toBe(plain.ground);
    expect(branded.ink).toBe(plain.ink);
    expect(branded.hairline).toBe(plain.hairline);
  });

  it('lifts the accent on dark so white button text stays readable', () => {
    // The reason the hand-picked pair moves #0080af to #22a5d1 on dark: these
    // accents are button fills carrying white labels.
    const darkAccent = getAuthTokens('dark', BRAND).accent;
    expect(getContrastRatio(darkAccent, '#030712')).toBeGreaterThan(
      getContrastRatio(BRAND, '#030712')
    );
  });
});
