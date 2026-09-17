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

/** Font weights loaded for brand fonts: light, regular, bold. */
const FONT_WEIGHTS = ['300', '400', '700'] as const;

export interface BrandFont {
  family: string;
  /**
   * `google` — loaded from the Google Fonts stylesheet.
   * `custom` — @font-face against `BRAND_FONT_BASE_URL`, one file per weight.
   * `org`    — @font-face against files the organisation uploaded, served by
   *            the `/brand-fonts` proxy from object storage.
   */
  source: 'google' | 'custom' | 'org';
  /** Google Fonts stylesheet URL (source === 'google'). */
  googleHref?: string;
  /** Base URL for self-hosted .ttf files (source === 'custom'). */
  baseUrl?: string;
  /** Slug used to build filenames: "Inria Sans" → "inria-sans". */
  slug: string;
  /**
   * Weights actually available (source === 'org'). An org may upload only
   * some of 300/400/700; the browser synthesises the rest from the nearest
   * one, so emitting an @font-face for a file that isn't there would be worse
   * than emitting none.
   */
  weights?: string[];
  /** Weight → file extension, for the `/brand-fonts` filenames (source === 'org'). */
  extensions?: Record<string, string>;
  /** Weight → content hash, appended to the file URL so a replacement busts caches. */
  sha256?: Record<string, string>;
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
export function normalizeFaviconUrl(
  value: string | undefined | null,
  // Named so the warning points at what to fix: an env var on a deployment,
  // the settings form on an organisation.
  source = 'BRAND_FAVICON_URL'
): string {
  const trimmed = value?.trim();
  if (!trimmed) return DEFAULT_FAVICON_URL;

  if (trimmed.startsWith('/')) {
    // `//host/icon.png` is protocol-relative: it looks root-relative but the
    // browser resolves it against an external host, inheriting the page's
    // scheme — so it would slip past the https check below. The backslash form
    // is here too because browsers normalise `/\` to `//`.
    if (/^\/[/\\]/.test(trimmed)) {
      console.warn(
        `[branding] Ignoring ${source} "${trimmed}": protocol-relative URLs point at an external host. Use an explicit https:// URL.`
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
      `[branding] Ignoring ${source} "${trimmed}": not a valid URL.`
    );
    return DEFAULT_FAVICON_URL;
  }

  if (parsed.protocol !== 'https:') {
    console.warn(
      `[branding] Ignoring ${source} "${trimmed}": only https:// URLs and root-relative paths are allowed.`
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
export function normalizeProductName(
  value: string | undefined | null,
  source = 'BRAND_PRODUCT_NAME'
): string {
  const trimmed = value?.trim();
  if (!trimmed) return DEFAULT_PRODUCT_NAME;

  if (trimmed.length > MAX_PRODUCT_NAME_LENGTH) {
    console.warn(
      `[branding] Ignoring ${source}: ${trimmed.length} characters exceeds the ${MAX_PRODUCT_NAME_LENGTH}-character limit.`
    );
    return DEFAULT_PRODUCT_NAME;
  }

  return trimmed;
}

const MAX_FONT_FAMILY_LENGTH = 80;

/** Letters, digits, spaces, hyphens. Rejects quotes, angle brackets, braces,
 *  and other characters that could break CSS or HTML injection boundaries. */
const SAFE_FONT_FAMILY_PATTERN = /^[a-zA-Z0-9 -]+$/;

export function slugifyFont(family: string): string {
  return family
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

/**
 * Validates a `BRAND_FONT_BASE_URL` — https:// or root-relative directory,
 * stripped of a trailing slash so callers can append `/{file}` directly.
 */
export function normalizeBaseUrl(
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

  if (!SAFE_FONT_FAMILY_PATTERN.test(family)) {
    console.warn(
      `[branding] Ignoring BRAND_FONT_FAMILY: "${family}" contains characters outside [a-zA-Z0-9 -].`
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

/**
 * Same-origin path serving the organisation's uploaded favicon. The route
 * handler resolves the org from the session and proxies the bytes out of
 * object storage — see `app/brand-assets/favicon/route.ts` for why the asset
 * is not linked directly.
 */
export const ORG_FAVICON_URL = '/brand-assets/favicon';

/** Length of content hash kept in an asset URL. 8 hex chars is 4 billion to one. */
const ASSET_VERSION_LENGTH = 8;

/**
 * Appends a content hash to an asset URL.
 *
 * Without this, replacing a favicon or a font file leaves the URL unchanged,
 * so every browser that already has the old bytes keeps showing them until its
 * cache entry expires — and favicons in particular are cached aggressively and
 * far past what the headers ask for. A content-addressed URL means a new file
 * is simply a different URL, which also lets the proxy routes serve them as
 * immutable.
 */
export function withAssetVersion(url: string, sha256?: string): string {
  if (!sha256) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}v=${sha256.slice(0, ASSET_VERSION_LENGTH)}`;
}

/**
 * Path prefix for organisation-uploaded assets.
 *
 * Callers rendering one must not hand it to `next/image`: the optimizer fetches
 * the URL server-side without the visitor's session cookie, and these routes
 * resolve the organisation from exactly that cookie. See `BrandMark`.
 */
const BRAND_ASSET_PREFIX = '/brand-assets/';

/** True when `url` is served by the session-scoped branding asset proxy. */
export function isBrandAssetUrl(url: string): boolean {
  return url.startsWith(BRAND_ASSET_PREFIX);
}

/** Base path the `@font-face` rules point at, for both custom and org fonts. */
export const BRAND_FONT_PROXY_BASE = '/brand-fonts';

/**
 * Filename a given weight of a brand font is served under.
 * Org fonts keep the uploaded extension; `BRAND_FONT_BASE_URL` fonts are .ttf.
 */
export function brandFontFileName(font: BrandFont, weight: string): string {
  const extension = font.extensions?.[weight] ?? '.ttf';
  return `${font.slug}-${weight}${extension}`;
}

/** The `@font-face` src for one weight, content-addressed when we know the hash. */
export function brandFontUrl(font: BrandFont, weight: string): string {
  return withAssetVersion(
    `${BRAND_FONT_PROXY_BASE}/${brandFontFileName(font, weight)}`,
    font.sha256?.[weight]
  );
}

/** Weights to emit `@font-face` rules for. */
export function brandFontWeights(font: BrandFont): readonly string[] {
  return font.weights?.length ? font.weights : FONT_WEIGHTS;
}

function orgBrandFont(
  font: OrganizationBrandFont | null | undefined
): BrandFont | undefined {
  if (!font?.family) return undefined;

  // Re-validated even though the backend rejects bad values on write: this
  // string is interpolated into a `<style>` block and a Google Fonts URL, and
  // a row written before that validation existed must not be trusted on the
  // strength of its age.
  if (
    font.family.length > MAX_FONT_FAMILY_LENGTH ||
    !SAFE_FONT_FAMILY_PATTERN.test(font.family)
  ) {
    console.warn(
      `[branding] Ignoring organisation brand font "${font.family}": contains characters outside [a-zA-Z0-9 -].`
    );
    return undefined;
  }

  // A Google family needs no files — the same stylesheet link the env-var
  // path uses carries it.
  if (font.source === 'google') {
    return {
      family: font.family,
      source: 'google',
      googleHref: buildGoogleFontsHref(font.family),
      slug: slugifyFont(font.family),
    };
  }

  // An upload with no files would emit @font-face rules pointing nowhere.
  if (!font.slug || !font.weights?.length) return undefined;

  return {
    family: font.family,
    source: 'org',
    slug: font.slug,
    weights: font.weights,
    extensions: font.extensions,
    sha256: font.sha256,
  };
}

/** The organisation-level branding fields this module consumes. */
interface OrganizationBrandFont {
  source?: 'google' | 'upload';
  family?: string;
  slug?: string | null;
  weights?: string[];
  extensions?: Record<string, string>;
  sha256?: Record<string, string>;
}

export interface OrganizationBranding {
  primary_color?: string | null;
  secondary_color?: string | null;
  product_name?: string | null;
  favicon?: { path?: string; sha256?: string } | null;
  font?: OrganizationBrandFont | null;
}

/**
 * Layers organisation branding over the deployment's env-var branding.
 *
 * Each field falls back on its own — an org that sets only a product name
 * keeps the deployment's `BRAND_PRIMARY_COLOR` — so clearing one field in the
 * settings form reveals the env var beneath it rather than resetting
 * everything to the Rhesis defaults.
 *
 * The font is the one exception: it resolves as a unit, because a family name
 * and the files that back it only make sense together.
 */
export function resolveBranding(
  deployment: Branding,
  org: OrganizationBranding | null | undefined
): Branding {
  if (!org) return deployment;

  const productName = org.product_name
    ? normalizeProductName(org.product_name, 'organisation product name')
    : deployment.productName;

  return {
    primaryColor:
      normalizeBrandColor(org.primary_color, 'organisation primary colour') ??
      deployment.primaryColor,
    secondaryColor:
      normalizeBrandColor(
        org.secondary_color,
        'organisation secondary colour'
      ) ?? deployment.secondaryColor,
    faviconUrl: org.favicon?.path
      ? withAssetVersion(ORG_FAVICON_URL, org.favicon.sha256)
      : deployment.faviconUrl,
    productName,
    isDefaultProductName: productName === DEFAULT_PRODUCT_NAME,
    font: orgBrandFont(org.font) ?? deployment.font,
  };
}

/** The deployment's `BRAND_*` values as seen from the browser. */
export interface DeploymentBranding {
  primaryColor?: string;
  secondaryColor?: string;
  faviconUrl?: string;
  productName?: string;
  fontFamily?: string;
}

/**
 * What an unset organisation branding field falls back to.
 *
 * Read from `window.__ENV__`, which the root layout fills with the
 * *deployment's* branding rather than the resolved one. Client code cannot
 * read `BRAND_*` directly: they carry no `NEXT_PUBLIC_` prefix, so every read
 * in a client bundle compiles to `undefined`.
 *
 * Returns an empty object on the server and before the inline script has run,
 * so callers get "nothing configured" rather than a crash.
 */
export function getDeploymentBranding(): DeploymentBranding {
  if (typeof window === 'undefined') return {};
  return window.__ENV__?.deploymentBranding ?? {};
}
