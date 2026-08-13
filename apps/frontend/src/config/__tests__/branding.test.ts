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
    expect(normalizeBrandColor('#6a1b9a')).toBe('#6A1B9A');
    expect(normalizeBrandColor('  #6A1B9A  ')).toBe('#6A1B9A');
  });

  it('treats absent and empty values as unset without warning', () => {
    expect(normalizeBrandColor(undefined)).toBeUndefined();
    expect(normalizeBrandColor('')).toBeUndefined();
    expect(normalizeBrandColor('   ')).toBeUndefined();
    expect(warn).not.toHaveBeenCalled();
  });

  it.each([
    ['#fff', 'the 3-digit form'],
    ['6A1B9A', 'a missing hash'],
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
      normalizeFaviconUrl('https://cdn.example.com/assets/favicon.png')
    ).toBe('https://cdn.example.com/assets/favicon.png');
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
    [
      '//example.com/favicon.png',
      'protocol-relative resolves to an external host',
    ],
    ['/\\example.com/favicon.png', 'browsers normalise /\\ to //'],
  ])('rejects %s (%s)', url => {
    expect(normalizeFaviconUrl(url)).toBe(DEFAULT_FAVICON_URL);
    expect(warn).toHaveBeenCalled();
  });

  it('still accepts an ordinary root-relative path with nested segments', () => {
    // The // guard must not catch a single leading slash followed by a path.
    expect(normalizeFaviconUrl('/assets/brand/icon.png')).toBe(
      '/assets/brand/icon.png'
    );
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
    expect(normalizeProductName('Acme')).toBe('Acme');
    expect(normalizeProductName('  Acme  ')).toBe('Acme');
  });

  it('preserves spacing and case inside the name', () => {
    expect(normalizeProductName('Acme AI Studio')).toBe('Acme AI Studio');
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
    secondary: process.env.BRAND_SECONDARY_COLOR,
    favicon: process.env.BRAND_FAVICON_URL,
    product: process.env.BRAND_PRODUCT_NAME,
  };

  // Assigning `undefined` to a process.env key stores the *string* "undefined"
  // rather than clearing it, which leaked a bogus BRAND_FAVICON_URL into the
  // next test and made it warn about the wrong variable. Delete instead.
  const restore = (key: string, value: string | undefined) => {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  };

  afterEach(() => {
    restore('BRAND_PRIMARY_COLOR', original.color);
    restore('BRAND_SECONDARY_COLOR', original.secondary);
    restore('BRAND_FAVICON_URL', original.favicon);
    restore('BRAND_PRODUCT_NAME', original.product);
  });

  it('reads every variable from the environment', () => {
    process.env.BRAND_PRIMARY_COLOR = '#6A1B9A';
    process.env.BRAND_SECONDARY_COLOR = '#C2185B';
    process.env.BRAND_FAVICON_URL = 'https://example.com/fav.png';
    process.env.BRAND_PRODUCT_NAME = 'Acme';

    expect(getServerBranding()).toEqual({
      primaryColor: '#6A1B9A',
      secondaryColor: '#C2185B',
      faviconUrl: 'https://example.com/fav.png',
      productName: 'Acme',
      isDefaultProductName: false,
    });
  });

  it('accepts a secondary colour on its own', () => {
    delete process.env.BRAND_PRIMARY_COLOR;
    process.env.BRAND_SECONDARY_COLOR = '#C2185B';

    const b = getServerBranding();
    expect(b.primaryColor).toBeUndefined();
    expect(b.secondaryColor).toBe('#C2185B');
  });

  it('names the offending variable when the secondary colour is malformed', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    process.env.BRAND_SECONDARY_COLOR = 'not-a-colour';

    expect(getServerBranding().secondaryColor).toBeUndefined();
    expect(
      warn.mock.calls.some(c => String(c[0]).includes('BRAND_SECONDARY_COLOR'))
    ).toBe(true);
    warn.mockRestore();
  });

  it('reports Rhesis defaults when nothing is configured', () => {
    delete process.env.BRAND_PRIMARY_COLOR;
    delete process.env.BRAND_SECONDARY_COLOR;
    delete process.env.BRAND_FAVICON_URL;
    delete process.env.BRAND_PRODUCT_NAME;

    expect(getServerBranding()).toEqual({
      primaryColor: undefined,
      secondaryColor: undefined,
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
