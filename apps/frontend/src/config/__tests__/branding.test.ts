import {
  DEFAULT_FAVICON_URL,
  DEFAULT_PRODUCT_NAME,
  getServerBranding,
  normalizeBrandColor,
  normalizeFaviconUrl,
  normalizeProductName,
} from '../branding';

describe('normalizeBrandColor', () => {
  let warn: jest.SpyInstance;

  beforeEach(() => {
    warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    warn.mockRestore();
  });

  it('accepts 6-digit hex and normalizes case', () => {
    expect(normalizeBrandColor('#005b33')).toBe('#005B33');
    expect(normalizeBrandColor('  #005B33  ')).toBe('#005B33');
  });

  it('treats absent and empty values as unset without warning', () => {
    expect(normalizeBrandColor(undefined)).toBeUndefined();
    expect(normalizeBrandColor('')).toBeUndefined();
    expect(normalizeBrandColor('   ')).toBeUndefined();
    expect(warn).not.toHaveBeenCalled();
  });

  it.each([
    ['#fff', 'the 3-digit form'],
    ['005B33', 'a missing hash'],
    ['green', 'a colour name'],
    ['#00zz33', 'non-hex digits'],
  ])('rejects %s (%s) and warns', color => {
    expect(normalizeBrandColor(color)).toBeUndefined();
    expect(warn).toHaveBeenCalled();
  });
});

describe('normalizeFaviconUrl', () => {
  let warn: jest.SpyInstance;

  beforeEach(() => {
    warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    warn.mockRestore();
  });

  it('accepts https URLs', () => {
    expect(
      normalizeFaviconUrl('https://www.netgo.de/hubfs/netgo_favicon.png')
    ).toBe('https://www.netgo.de/hubfs/netgo_favicon.png');
  });

  it('accepts root-relative paths', () => {
    expect(normalizeFaviconUrl('/logos/custom.png')).toBe('/logos/custom.png');
  });

  it('falls back to the default when unset', () => {
    expect(normalizeFaviconUrl(undefined)).toBe(DEFAULT_FAVICON_URL);
    expect(normalizeFaviconUrl('')).toBe(DEFAULT_FAVICON_URL);
    expect(warn).not.toHaveBeenCalled();
  });

  it.each([
    ['http://example.com/favicon.png', 'plain http would be mixed content'],
    ['javascript:alert(1)', 'a script URL must never reach <head>'],
    ['data:image/png;base64,AAAA', 'other schemes are not allowed'],
    ['not a url', 'unparseable'],
    ['example.com/favicon.png', 'scheme-less is unparseable'],
  ])('rejects %s (%s)', url => {
    expect(normalizeFaviconUrl(url)).toBe(DEFAULT_FAVICON_URL);
    expect(warn).toHaveBeenCalled();
  });
});

describe('normalizeProductName', () => {
  let warn: jest.SpyInstance;

  beforeEach(() => {
    warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    warn.mockRestore();
  });

  it('accepts a name and trims surrounding whitespace', () => {
    expect(normalizeProductName('Netgo')).toBe('Netgo');
    expect(normalizeProductName('  Netgo  ')).toBe('Netgo');
  });

  it('preserves spacing and case inside the name', () => {
    expect(normalizeProductName('netgo AI Studio')).toBe('netgo AI Studio');
  });

  it('falls back to the default when unset', () => {
    expect(normalizeProductName(undefined)).toBe(DEFAULT_PRODUCT_NAME);
    expect(normalizeProductName('   ')).toBe(DEFAULT_PRODUCT_NAME);
    expect(warn).not.toHaveBeenCalled();
  });

  it('rejects an over-long name rather than truncating it', () => {
    expect(normalizeProductName('N'.repeat(61))).toBe(DEFAULT_PRODUCT_NAME);
    expect(warn).toHaveBeenCalled();
    expect(normalizeProductName('N'.repeat(60))).toHaveLength(60);
  });
});

describe('getServerBranding', () => {
  const original = {
    color: process.env.BRAND_PRIMARY_COLOR,
    favicon: process.env.BRAND_FAVICON_URL,
    product: process.env.BRAND_PRODUCT_NAME,
  };

  afterEach(() => {
    process.env.BRAND_PRIMARY_COLOR = original.color;
    process.env.BRAND_FAVICON_URL = original.favicon;
    process.env.BRAND_PRODUCT_NAME = original.product;
  });

  it('reads every variable from the environment', () => {
    process.env.BRAND_PRIMARY_COLOR = '#005B33';
    process.env.BRAND_FAVICON_URL = 'https://example.com/fav.png';
    process.env.BRAND_PRODUCT_NAME = 'Netgo';

    expect(getServerBranding()).toEqual({
      primaryColor: '#005B33',
      faviconUrl: 'https://example.com/fav.png',
      productName: 'Netgo',
      isDefaultProductName: false,
    });
  });

  it('reports Rhesis defaults when nothing is configured', () => {
    delete process.env.BRAND_PRIMARY_COLOR;
    delete process.env.BRAND_FAVICON_URL;
    delete process.env.BRAND_PRODUCT_NAME;

    expect(getServerBranding()).toEqual({
      primaryColor: undefined,
      faviconUrl: DEFAULT_FAVICON_URL,
      productName: DEFAULT_PRODUCT_NAME,
      isDefaultProductName: true,
    });
  });

  it('flags an explicit "Rhesis AI" as the default, not an override', () => {
    // Keeps the Rhesis marketing description on a deployment that sets the name
    // to what it already was.
    process.env.BRAND_PRODUCT_NAME = 'Rhesis AI';
    expect(getServerBranding().isDefaultProductName).toBe(true);
  });
});
