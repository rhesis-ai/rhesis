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
    fontFamily: process.env.BRAND_FONT_FAMILY,
    fontBaseUrl: process.env.BRAND_FONT_BASE_URL,
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
    restore('BRAND_FONT_FAMILY', original.fontFamily);
    restore('BRAND_FONT_BASE_URL', original.fontBaseUrl);
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
      font: undefined,
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
      font: undefined,
    });
  });

  it('flags an explicit "Rhesis AI" as the default, not an override', () => {
    // Keeps the Rhesis marketing description on a deployment that sets the name
    // to what it already was.
    process.env.BRAND_PRODUCT_NAME = 'Rhesis AI';
    expect(getServerBranding().isDefaultProductName).toBe(true);
  });

  describe('font', () => {
    let warn: jest.SpyInstance;

    beforeEach(() => {
      warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
      delete process.env.BRAND_FONT_FAMILY;
      delete process.env.BRAND_FONT_BASE_URL;
    });

    afterEach(() => {
      warn.mockRestore();
    });

    it('returns google source with correct href when only family is set', () => {
      process.env.BRAND_FONT_FAMILY = 'Inria Sans';

      const font = getServerBranding().font;
      expect(font).toEqual({
        family: 'Inria Sans',
        source: 'google',
        googleHref:
          'https://fonts.googleapis.com/css2?family=Inria%20Sans:wght@300;400;700&display=swap',
        slug: 'inria-sans',
      });
    });

    it('returns custom source when family and base URL are set', () => {
      process.env.BRAND_FONT_FAMILY = 'Inria Sans';
      process.env.BRAND_FONT_BASE_URL = 'https://gitea.example.com/fonts';

      const font = getServerBranding().font;
      expect(font).toEqual({
        family: 'Inria Sans',
        source: 'custom',
        baseUrl: 'https://gitea.example.com/fonts',
        slug: 'inria-sans',
      });
    });

    it('strips trailing slashes from the base URL', () => {
      process.env.BRAND_FONT_FAMILY = 'Fira Code';
      process.env.BRAND_FONT_BASE_URL = 'https://cdn.example.com/fonts///';

      expect(getServerBranding().font?.baseUrl).toBe(
        'https://cdn.example.com/fonts'
      );
    });

    it('accepts root-relative base URL', () => {
      process.env.BRAND_FONT_FAMILY = 'Fira Code';
      process.env.BRAND_FONT_BASE_URL = '/static/fonts';

      const font = getServerBranding().font;
      expect(font?.source).toBe('custom');
      expect(font?.baseUrl).toBe('/static/fonts');
    });

    it('ignores invalid base URL and falls back to google', () => {
      process.env.BRAND_FONT_FAMILY = 'Fira Code';
      process.env.BRAND_FONT_BASE_URL = 'http://insecure.example.com/fonts';

      const font = getServerBranding().font;
      expect(font?.source).toBe('google');
      expect(warn).toHaveBeenCalled();
    });

    it('rejects protocol-relative base URL', () => {
      process.env.BRAND_FONT_FAMILY = 'Fira Code';
      process.env.BRAND_FONT_BASE_URL = '//cdn.example.com/fonts';

      const font = getServerBranding().font;
      expect(font?.source).toBe('google');
      expect(warn).toHaveBeenCalled();
    });

    it('returns undefined when family is unset', () => {
      expect(getServerBranding().font).toBeUndefined();
      expect(warn).not.toHaveBeenCalled();
    });

    it('rejects an overlong family name', () => {
      process.env.BRAND_FONT_FAMILY = 'A'.repeat(81);

      expect(getServerBranding().font).toBeUndefined();
      expect(warn).toHaveBeenCalled();
    });

    it('slugifies family names with hyphens', () => {
      process.env.BRAND_FONT_FAMILY = 'IBM Plex Sans';

      expect(getServerBranding().font?.slug).toBe('ibm-plex-sans');
    });

    it.each([
      ['Noto Sans (Display)', 'parentheses'],
      ['Font "Name"', 'double quotes'],
      ["Font 'Name'", 'single quotes'],
      ['Font</style>', 'angle brackets'],
      ['Font{Name}', 'curly braces'],
    ])('rejects %s (%s) with unsafe characters', family => {
      process.env.BRAND_FONT_FAMILY = family;

      expect(getServerBranding().font).toBeUndefined();
      expect(warn).toHaveBeenCalled();
    });
  });
});
