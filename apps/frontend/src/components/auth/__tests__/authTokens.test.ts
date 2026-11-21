import { blend, getContrastRatio } from '@mui/system/colorManipulator';
import { AURORA_BLOOM, getAuthTokens } from '../authTokens';

/** A dark brand colour, far enough from Rhesis blue to make swaps obvious. */
const BRAND = '#6A1B9A';

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
    expect(light.accent).toBe('#6a1b9a');
    expect(light.accentShadow).toContain('rgba(106, 27, 154, 0.55)');
  });

  it('leaves the non-accent tokens alone', () => {
    // Only the accent tokens are brand-driven; ground, ink and the
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

  it('makes a navy brand colour readable on the dark ground', () => {
    // The old fixed lighten(0.13) left a navy at ~1.8:1 — the headline
    // accents and the email button were invisible.
    const t = getAuthTokens('dark', '#0B1E4D');
    expect(getContrastRatio(t.accent, t.ground)).toBeGreaterThanOrEqual(4.5);
  });

  it('measures the dark accent against the aurora, not the bare ground', () => {
    // The headline sits on the aurora's blue bloom; a navy lifted only to
    // clear #030712 measured ~2.3:1 there.
    const t = getAuthTokens('dark', '#0B1E4D');
    const peak = blend(t.ground, AURORA_BLOOM.color, AURORA_BLOOM.opacity);
    expect(getContrastRatio(t.accent, peak)).toBeGreaterThanOrEqual(3);
  });

  it('darkens a pale brand colour on the light ground', () => {
    const t = getAuthTokens('light', '#FDD803');
    expect(getContrastRatio(t.accent, t.ground)).toBeGreaterThanOrEqual(3);
  });

  it('leaves a brand colour that already reads exactly as configured', () => {
    expect(getAuthTokens('dark', '#FDD803').accent).toBe('#fdd803');
    expect(getAuthTokens('light', '#0080AF').accent).toBe('#0080af');
  });
});

describe('getAuthTokens in accessibility mode', () => {
  it.each([
    ['light', undefined],
    ['dark', undefined],
    ['light', '#FDD803'],
    ['dark', '#0D1B2A'],
  ] as const)(
    'keeps %s accent and muted text at 4.5:1 (brand %s)',
    (mode, brand) => {
      const t = getAuthTokens(mode, brand, true);
      for (const color of [t.accent, t.muted]) {
        expect(getContrastRatio(color, t.ground)).toBeGreaterThanOrEqual(4.5);
      }
    }
  );

  it('changes nothing when off', () => {
    expect(getAuthTokens('light', undefined, false)).toEqual(
      getAuthTokens('light')
    );
  });
});
