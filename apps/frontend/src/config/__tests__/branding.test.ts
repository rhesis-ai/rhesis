import {
  DEFAULT_FAVICON_URL,
  DEFAULT_PRODUCT_NAME,
  ORG_FAVICON_URL,
  brandFontFileName,
  brandFontUrl,
  brandFontWeights,
  withAssetVersion,
  getServerBranding,
  normalizeBrandColor,
  normalizeFaviconUrl,
  normalizeProductName,
  resolveBranding,
  type BrandFont,
  type Branding,
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

describe('resolveBranding', () => {
  let warn: jest.SpyInstance;

  beforeEach(() => {
    warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    warn.mockRestore();
  });

  const deployment: Branding = {
    primaryColor: '#111111',
    secondaryColor: '#222222',
    faviconUrl: '/deployment-icon.svg',
    productName: 'Deployment',
    isDefaultProductName: false,
    font: {
      family: 'Deployment Sans',
      source: 'google',
      slug: 'deployment-sans',
      googleHref: 'https://fonts.googleapis.com/css2?family=Deployment+Sans',
    },
  };

  it('returns the deployment branding untouched when the org has none', () => {
    expect(resolveBranding(deployment, null)).toEqual(deployment);
    expect(resolveBranding(deployment, undefined)).toEqual(deployment);
    expect(resolveBranding(deployment, {})).toEqual(deployment);
  });

  it('overrides only the fields the org sets', () => {
    const resolved = resolveBranding(deployment, { product_name: 'Acme' });

    expect(resolved.productName).toBe('Acme');
    expect(resolved.primaryColor).toBe('#111111');
    expect(resolved.secondaryColor).toBe('#222222');
    expect(resolved.faviconUrl).toBe('/deployment-icon.svg');
  });

  it('normalizes org colours the same way as env vars', () => {
    const resolved = resolveBranding(deployment, { primary_color: '#6a1b9a' });

    expect(resolved.primaryColor).toBe('#6A1B9A');
  });

  it('falls back to the deployment value when an org colour is malformed', () => {
    const resolved = resolveBranding(deployment, { primary_color: '#fff' });

    expect(resolved.primaryColor).toBe('#111111');
    expect(warn).toHaveBeenCalled();
  });

  it('treats a cleared org field as unset rather than empty', () => {
    const resolved = resolveBranding(deployment, {
      primary_color: null,
      product_name: null,
    });

    expect(resolved.primaryColor).toBe('#111111');
    expect(resolved.productName).toBe('Deployment');
  });

  it('points the favicon at the org asset proxy once one is uploaded', () => {
    const resolved = resolveBranding(deployment, {
      favicon: { path: 'branding/org-1/favicon.png' },
    });

    expect(resolved.faviconUrl).toBe(ORG_FAVICON_URL);
  });

  it('content-addresses the favicon so a replacement busts browser caches', () => {
    // The path never changes when the bytes do, and favicons are cached hard.
    const resolved = resolveBranding(deployment, {
      favicon: {
        path: 'branding/org-1/favicon.png',
        sha256: 'abcdef1234567890',
      },
    });

    expect(resolved.faviconUrl).toBe(`${ORG_FAVICON_URL}?v=abcdef12`);
  });

  it('resolves an org font as a unit, replacing the deployment font', () => {
    const resolved = resolveBranding(deployment, {
      font: {
        source: 'upload',
        family: 'Inria Sans',
        slug: 'inria-sans',
        weights: ['400', '700'],
        extensions: { '400': '.woff2', '700': '.ttf' },
      },
    });

    expect(resolved.font).toEqual({
      family: 'Inria Sans',
      source: 'org',
      slug: 'inria-sans',
      weights: ['400', '700'],
      extensions: { '400': '.woff2', '700': '.ttf' },
    });
  });

  it('keeps the deployment font when an org upload has no weights', () => {
    // An upload with no files would emit @font-face rules pointing nowhere.
    const resolved = resolveBranding(deployment, {
      font: {
        source: 'upload',
        family: 'Inria Sans',
        slug: 'inria-sans',
        weights: [],
      },
    });

    expect(resolved.font).toBe(deployment.font);
  });

  it('resolves an org Google font to a stylesheet link, with no files', () => {
    const resolved = resolveBranding(deployment, {
      font: { source: 'google', family: 'Open Sans' },
    });

    expect(resolved.font).toMatchObject({
      family: 'Open Sans',
      source: 'google',
      slug: 'open-sans',
    });
    expect(resolved.font?.googleHref).toContain('family=Open%20Sans');
    expect(resolved.font?.googleHref).toContain('wght@300;400;700');
  });

  it('needs no slug or weights for an org Google font', () => {
    // Unlike an upload, there are no files to point at.
    const resolved = resolveBranding(deployment, {
      font: { source: 'google', family: 'Roboto' },
    });

    expect(resolved.font?.source).toBe('google');
  });

  it.each([
    ['Font</style>', 'angle brackets'],
    ['Font "Name"', 'double quotes'],
  ])('rejects an org font family with %s (%s)', family => {
    const resolved = resolveBranding(deployment, {
      font: { source: 'upload', family, slug: 'x', weights: ['400'] },
    });

    expect(resolved.font).toBe(deployment.font);
    expect(warn).toHaveBeenCalled();
  });

  it('reports isDefaultProductName for an org that clears its name', () => {
    const rhesisDefault: Branding = {
      ...deployment,
      productName: DEFAULT_PRODUCT_NAME,
      isDefaultProductName: true,
    };

    expect(
      resolveBranding(rhesisDefault, { product_name: null })
    ).toMatchObject({
      productName: DEFAULT_PRODUCT_NAME,
      isDefaultProductName: true,
    });
  });
});

describe('brandFontFileName', () => {
  it('uses the uploaded extension for an org font', () => {
    const font: BrandFont = {
      family: 'Inria Sans',
      source: 'org',
      slug: 'inria-sans',
      weights: ['400'],
      extensions: { '400': '.woff2' },
    };

    expect(brandFontFileName(font, '400')).toBe('inria-sans-400.woff2');
  });

  it('defaults to .ttf for a BRAND_FONT_BASE_URL font', () => {
    const font: BrandFont = {
      family: 'Inria Sans',
      source: 'custom',
      slug: 'inria-sans',
      baseUrl: 'https://fonts.example.com',
    };

    expect(brandFontFileName(font, '300')).toBe('inria-sans-300.ttf');
  });
});

describe('brandFontWeights', () => {
  it('uses the org font’s own weights', () => {
    expect(
      brandFontWeights({
        family: 'Inria Sans',
        source: 'org',
        slug: 'inria-sans',
        weights: ['400'],
      })
    ).toEqual(['400']);
  });

  it('falls back to all three weights when none are recorded', () => {
    expect(
      brandFontWeights({
        family: 'Inria Sans',
        source: 'custom',
        slug: 'inria-sans',
      })
    ).toEqual(['300', '400', '700']);
  });
});

describe('brandFontUrl', () => {
  const uploaded: BrandFont = {
    family: 'Inria Sans',
    source: 'org',
    slug: 'inria-sans',
    weights: ['400'],
    extensions: { '400': '.woff2' },
    sha256: { '400': 'feedface00000000' },
  };

  it('content-addresses an uploaded weight', () => {
    expect(brandFontUrl(uploaded, '400')).toBe(
      '/brand-fonts/inria-sans-400.woff2?v=feedface'
    );
  });

  it('omits the version when no hash is recorded', () => {
    // A BRAND_FONT_BASE_URL font is fetched from a server we do not control
    // and has no hash; the plain filename is all we can ask for.
    const envFont: BrandFont = {
      family: 'Inria Sans',
      source: 'custom',
      slug: 'inria-sans',
      baseUrl: 'https://fonts.example.com',
    };

    expect(brandFontUrl(envFont, '300')).toBe(
      '/brand-fonts/inria-sans-300.ttf'
    );
  });
});

describe('withAssetVersion', () => {
  it('appends a truncated hash', () => {
    expect(withAssetVersion('/a', '0123456789abcdef')).toBe('/a?v=01234567');
  });

  it('returns the url untouched when there is no hash', () => {
    expect(withAssetVersion('/a', undefined)).toBe('/a');
  });

  it('uses & when the url already has a query string', () => {
    expect(withAssetVersion('/a?b=c', '0123456789abcdef')).toBe(
      '/a?b=c&v=01234567'
    );
  });
});
