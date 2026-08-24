/**
 * Runtime branding overrides, for deployments that need their own colour, icon
 * and product name (white-label / on-prem installs).
 *
 * All three are plain env vars, deliberately *without* the `NEXT_PUBLIC_`
 * prefix: that prefix inlines a value into the client bundle at build time,
 * which would mean one Docker image per deployment. These are read on the
 * server at request time and handed to the client via props and
 * `window.__ENV__` — the same route `API_BASE_URL` already takes (see
 * `url-resolver.ts`).
 *
 * In Kubernetes they arrive from the chart's ConfigMap, which every app
 * deployment already loads with `envFrom`. None of them is a secret — all three
 * end up visible in the served HTML — so they do not belong in Secret Manager.
 */

/** Shipped Rhesis favicon, used whenever no override is configured. */
export const DEFAULT_FAVICON_URL = '/logos/rhesis-logo-favicon.svg';

/** Product name in page titles, the sidebar and image alt text. */
export const DEFAULT_PRODUCT_NAME = 'Rhesis AI';

/** Long enough for a real product name, short enough to keep `<title>` sane. */
const MAX_PRODUCT_NAME_LENGTH = 60;

/** 6-digit hex only: MUI's colour manipulators need a parseable value, and the
 * 3-digit form would silently widen what deployments can put in a values file. */
const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

/** Font weights the theme uses: light, regular, bold. */
const FONT_WEIGHTS = ['300', '400', '700'] as const;

export interface BrandFont {
  family: string;
  source: 'google' | 'custom';
  /** Google Fonts stylesheet URL (source === 'google'). */
  googleHref?: string;
  /** Base URL for self-hosted .ttf files (source === 'custom'). */
  baseUrl?: string;
  /** Slug used to build filenames: "Inria Sans" → "inria-sans". */
  slug: string;
}

export interface Branding {
  /** Undefined means "use the built-in Rhesis palette", not "no colour". */
  primaryColor?: string;
  /** Secondary/CTA colour. Independent of `primaryColor` — a deployment can set
   * either on its own. */
  secondaryColor?: string;
  faviconUrl: string;
  productName: string;
  /** True when `productName` is the Rhesis default, so callers can keep
   * Rhesis-specific copy (the marketing description) out of a branded build. */
  isDefaultProductName: boolean;
  /** Custom font override. Undefined means "use Be Vietnam Pro". */
  font?: BrandFont;
}

/**
 * Validates a configured brand colour, returning undefined when it is absent
 * or malformed. A typo in a values file must fall back to the Rhesis palette
 * rather than take the app down or paint half the UI `undefined`.
 */
export function normalizeBrandColor(
  value: string | undefined | null,
  // Named so the warning tells the operator which variable to go and fix.
  varName = 'BRAND_PRIMARY_COLOR'
): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;

  if (!HEX_COLOR_PATTERN.test(trimmed)) {
    console.warn(
      `[branding] Ignoring ${varName} "${trimmed}": expected a 6-digit hex colour in #RRGGBB form.`
    );
    return undefined;
  }

  return trimmed.toUpperCase();
}

/**
 * Validates a configured favicon URL, falling back to the Rhesis default.
 *
 * Only absolute `https://` URLs and root-relative paths are accepted. `http://`
 * is rejected because it would make an https page issue a mixed-content
 * request, and rejecting every other scheme keeps `javascript:` out of an
 * attribute we render into `<head>`.
 */
export function normalizeFaviconUrl(value: string | undefined | null): string {
  const trimmed = value?.trim();
  if (!trimmed) return DEFAULT_FAVICON_URL;

  if (trimmed.startsWith('/')) {
    // `//host/icon.png` is protocol-relative: it looks root-relative but the
    // browser resolves it against an external host, inheriting the page's
    // scheme — so it would slip past the https check below. The backslash form
    // is here too because browsers normalise `/\` to `//`.
    if (/^\/[/\\]/.test(trimmed)) {
      console.warn(
        `[branding] Ignoring BRAND_FAVICON_URL "${trimmed}": protocol-relative URLs point at an external host. Use an explicit https:// URL.`
      );
      return DEFAULT_FAVICON_URL;
    }
    return trimmed;
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    console.warn(
      `[branding] Ignoring BRAND_FAVICON_URL "${trimmed}": not a valid URL.`
    );
    return DEFAULT_FAVICON_URL;
  }

  if (parsed.protocol !== 'https:') {
    console.warn(
      `[branding] Ignoring BRAND_FAVICON_URL "${trimmed}": only https:// URLs and root-relative paths are allowed.`
    );
    return DEFAULT_FAVICON_URL;
  }

  return parsed.toString();
}

/**
 * Validates a configured product name — the `%s | <name>` suffix on every page
 * title, and the fallback shown in the sidebar before the organisation loads.
 *
 * Over-long values are rejected rather than truncated: a cut-off name in the
 * browser tab is harder to diagnose than the default reappearing next to a
 * warning.
 */
export function normalizeProductName(value: string | undefined | null): string {
  const trimmed = value?.trim();
  if (!trimmed) return DEFAULT_PRODUCT_NAME;

  if (trimmed.length > MAX_PRODUCT_NAME_LENGTH) {
    console.warn(
      `[branding] Ignoring BRAND_PRODUCT_NAME: ${trimmed.length} characters exceeds the ${MAX_PRODUCT_NAME_LENGTH}-character limit.`
    );
    return DEFAULT_PRODUCT_NAME;
  }

  return trimmed;
}

const MAX_FONT_FAMILY_LENGTH = 80;

function slugifyFont(family: string): string {
  return family.toLowerCase().replace(/\s+/g, '-');
}

/**
 * Validates a `BRAND_FONT_BASE_URL` — https:// or root-relative directory,
 * stripped of a trailing slash so callers can append `/{file}` directly.
 */
function normalizeBaseUrl(
  value: string | undefined | null
): string | undefined {
  const trimmed = value?.trim().replace(/\/+$/, '');
  if (!trimmed) return undefined;

  if (trimmed.startsWith('/')) {
    if (/^\/[/\\]/.test(trimmed)) {
      console.warn(
        `[branding] Ignoring BRAND_FONT_BASE_URL "${trimmed}": protocol-relative URLs are not allowed.`
      );
      return undefined;
    }
    return trimmed;
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    console.warn(
      `[branding] Ignoring BRAND_FONT_BASE_URL "${trimmed}": not a valid URL.`
    );
    return undefined;
  }

  if (parsed.protocol !== 'https:') {
    console.warn(
      `[branding] Ignoring BRAND_FONT_BASE_URL "${trimmed}": only https:// URLs and root-relative paths are allowed.`
    );
    return undefined;
  }

  return parsed.toString().replace(/\/+$/, '');
}

function buildGoogleFontsHref(family: string): string {
  const weights = FONT_WEIGHTS.join(';');
  const encoded = encodeURIComponent(family);
  return `https://fonts.googleapis.com/css2?family=${encoded}:wght@${weights}&display=swap`;
}

/**
 * Reads `BRAND_FONT_FAMILY` (required) and `BRAND_FONT_BASE_URL` (optional)
 * from the environment.
 *
 * When only the family is set, the font is loaded from Google Fonts. When a
 * base URL is also provided, `@font-face` rules are generated from
 * `{baseUrl}/{slug}-{weight}.ttf` instead — for air-gapped or self-hosted
 * deployments that can't reach Google.
 */
function normalizeBrandFont(): BrandFont | undefined {
  const family = process.env.BRAND_FONT_FAMILY?.trim();
  if (!family) return undefined;

  if (family.length > MAX_FONT_FAMILY_LENGTH) {
    console.warn(
      `[branding] Ignoring BRAND_FONT_FAMILY: ${family.length} characters exceeds the ${MAX_FONT_FAMILY_LENGTH}-character limit.`
    );
    return undefined;
  }

  const slug = slugifyFont(family);
  const baseUrl = normalizeBaseUrl(process.env.BRAND_FONT_BASE_URL);

  if (baseUrl) {
    return { family, source: 'custom', baseUrl, slug };
  }

  return {
    family,
    source: 'google',
    googleHref: buildGoogleFontsHref(family),
    slug,
  };
}

/**
 * Reads branding from the environment. Server-side only — the env vars carry no
 * `NEXT_PUBLIC_` prefix, so in a client bundle every read compiles to
 * `undefined` and this would quietly report the defaults.
 */
export function getServerBranding(): Branding {
  const productName = normalizeProductName(process.env.BRAND_PRODUCT_NAME);

  return {
    primaryColor: normalizeBrandColor(process.env.BRAND_PRIMARY_COLOR),
    secondaryColor: normalizeBrandColor(
      process.env.BRAND_SECONDARY_COLOR,
      'BRAND_SECONDARY_COLOR'
    ),
    faviconUrl: normalizeFaviconUrl(process.env.BRAND_FAVICON_URL),
    productName,
    isDefaultProductName: productName === DEFAULT_PRODUCT_NAME,
    font: normalizeBrandFont(),
  };
}
