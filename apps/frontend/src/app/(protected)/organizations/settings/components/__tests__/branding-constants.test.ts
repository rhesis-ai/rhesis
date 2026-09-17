import {
  MIN_FAVICON_DIMENSION,
  RECOMMENDED_FAVICON_DIMENSION,
  describeFaviconSize,
  faviconWarning,
  formatBytes,
} from '../branding-constants';

describe('faviconWarning', () => {
  it('says nothing about a large square icon', () => {
    expect(
      faviconWarning({
        width: RECOMMENDED_FAVICON_DIMENSION,
        height: RECOMMENDED_FAVICON_DIMENSION,
      })
    ).toBeNull();
  });

  it('says nothing about an SVG, which has no fixed raster size', () => {
    expect(faviconWarning({ width: null, height: null })).toBeNull();
  });

  it('says nothing when there is no favicon at all', () => {
    expect(faviconWarning(undefined)).toBeNull();
    expect(faviconWarning(null)).toBeNull();
  });

  it('flags a non-square icon and reports its dimensions', () => {
    const warning = faviconWarning({ width: 512, height: 256 });

    expect(warning).toContain('512 x 256');
    expect(warning).toContain('not square');
  });

  it('prefers the squareness complaint over the size one', () => {
    // A 64x32 icon is both oblong and too small; letterboxing is the more
    // visible problem and the one worth naming first.
    expect(faviconWarning({ width: 64, height: 32 })).toContain('not square');
  });

  it('flags a square icon that is too small to stay sharp', () => {
    const warning = faviconWarning({ width: 32, height: 32 });

    expect(warning).toContain('32 x 32');
    expect(warning).toContain(String(RECOMMENDED_FAVICON_DIMENSION));
  });

  it('accepts an icon exactly at the minimum', () => {
    expect(
      faviconWarning({
        width: MIN_FAVICON_DIMENSION,
        height: MIN_FAVICON_DIMENSION,
      })
    ).toBeNull();
  });
});

describe('describeFaviconSize', () => {
  it('reports pixel dimensions for a raster icon', () => {
    expect(describeFaviconSize({ width: 512, height: 512 })).toBe('512 x 512');
  });

  it('reports an SVG as scalable', () => {
    expect(describeFaviconSize({ width: null, height: null })).toBe('Scalable');
  });
});

describe('formatBytes', () => {
  it.each([
    [512, '512 B'],
    [1024, '1 KB'],
    [512 * 1024, '512 KB'],
    [2 * 1024 * 1024, '2.0 MB'],
  ])('formats %i as %s', (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected);
  });
});
