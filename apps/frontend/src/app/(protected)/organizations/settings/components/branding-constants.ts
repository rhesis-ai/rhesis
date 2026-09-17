import type {
  BrandingFavicon,
  BrandingSettings,
  Organization,
} from '@/utils/api-client/interfaces/organization';

/** Mirrors the backend's HEX_COLOR_PATTERN, so the form rejects what a PATCH would. */
export const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;

/** Rhesis theme defaults, used when no deployment branding is configured. */
export const RHESIS_PRIMARY_COLOR = '#0080AF'; // Intentional: brand default, not a style
export const RHESIS_SECONDARY_COLOR = '#FD6E12'; // Intentional: brand default, not a style

export const MAX_PRODUCT_NAME_LENGTH = 60;
export const MAX_FONT_FAMILY_LENGTH = 80;

/** Mirrors the backend's SAFE_FONT_FAMILY_PATTERN. */
export const SAFE_FONT_FAMILY_PATTERN = /^[a-zA-Z0-9 -]+$/;

/** Weights a brand font can supply: light, regular, bold. */
export const FONT_WEIGHTS = ['300', '400', '700'] as const;

export type FontWeight = (typeof FONT_WEIGHTS)[number];

/** Human label per weight, for the upload rows. */
export const FONT_WEIGHT_LABELS: Record<FontWeight, string> = {
  '300': 'Light (300)',
  '400': 'Regular (400)',
  '700': 'Bold (700)',
};

/** Accepted favicon types, as an `accept` attribute and for client-side checks. */
export const FAVICON_ACCEPT = '.png,.svg,.ico,.webp,.jpg,.jpeg,.gif';

/**
 * Below this the mark looks soft. The largest place it renders is the
 * onboarding header at 92 CSS px, which is 184 device px on a 2x display.
 * Mirrors MIN_FAVICON_DIMENSION in the backend schema.
 */
export const MIN_FAVICON_DIMENSION = 192;

/** What we tell operators to upload — comfortable at every render size. */
export const RECOMMENDED_FAVICON_DIMENSION = 512;

export const FONT_ACCEPT = '.ttf,.otf,.woff,.woff2';

/** Matches MAX_FAVICON_BYTES in the backend's branding service. */
export const MAX_FAVICON_BYTES = 512 * 1024;

/** Matches MAX_FONT_BYTES in the backend's branding service. */
export const MAX_FONT_BYTES = 2 * 1024 * 1024;

/** The organization's branding block, or undefined when it has none yet. */
export function brandingOf(
  organization: Organization
): BrandingSettings | undefined {
  return organization.organization_settings?.branding;
}

/**
 * Human-readable problem with an uploaded favicon, or null when it is fine.
 *
 * A warning, never a block: a small or oblong icon still works, it just looks
 * worse, and refusing the upload would be a worse trade than telling them.
 * SVG carries no dimensions, so there is nothing to check.
 */
export function faviconWarning(
  favicon: Pick<BrandingFavicon, 'width' | 'height'> | null | undefined
): string | null {
  if (!favicon?.width || !favicon.height) return null;

  const { width, height } = favicon;

  if (width !== height) {
    return `This icon is ${width} x ${height}, not square. It will be letterboxed to fit.`;
  }

  if (width < MIN_FAVICON_DIMENSION) {
    return `This icon is ${width} x ${height}. Upload at least ${RECOMMENDED_FAVICON_DIMENSION} x ${RECOMMENDED_FAVICON_DIMENSION} so it stays sharp on high-density screens.`;
  }

  return null;
}

/** "512 x 512", or "Scalable" for an SVG. */
export function describeFaviconSize(
  favicon: Pick<BrandingFavicon, 'width' | 'height'> | null | undefined
): string {
  if (!favicon?.width || !favicon.height) return 'Scalable';
  return `${favicon.width} x ${favicon.height}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
