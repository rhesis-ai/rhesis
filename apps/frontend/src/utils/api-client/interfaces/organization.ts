import type { Currency } from '@/utils/money';

import { UUID } from 'crypto';

/** Server-owned descriptor for an uploaded favicon, written by the upload endpoint. */
export interface BrandingFavicon {
  path: string;
  content_type: string;
  filename: string;
  sha256: string;
  /** Pixel dimensions recorded at upload. Null for SVG, which has no fixed raster size. */
  width?: number | null;
  height?: number | null;
}

/** The organization's brand font, from Google Fonts or uploaded files. */
export interface BrandingFont {
  source: 'google' | 'upload';
  family: string;
  /** Upload only — the filename stem the @font-face rules request. */
  slug?: string | null;
  /** Uploaded weights, a subset of 300/400/700. Empty for a Google font. */
  weights: string[];
  extensions: Record<string, string>;
  sha256: Record<string, string>;
}

/** The writable font shape: a Google family, or null to clear. */
export interface BrandingGoogleFont {
  source: 'google';
  family: string;
}

/**
 * Per-organization white-label branding. Every field falls back independently:
 * an unset value uses the deployment's `BRAND_*` env var, then the Rhesis
 * default. See `resolveBranding` in `@/config/branding`.
 */
export interface BrandingSettings {
  primary_color?: string | null;
  secondary_color?: string | null;
  product_name?: string | null;
  favicon?: BrandingFavicon | null;
  font?: BrandingFont | null;
}

/** How figures are shown to everyone in the organization. */
export interface DisplaySettings {
  /** Unset means costs show in the currency they are stored in. */
  currency?: Currency | null;
}

export interface OrganizationSettings {
  version: number;
  branding: BrandingSettings;
  display?: DisplaySettings;
}

export interface OrganizationSettingsRead extends OrganizationSettings {
  permitted_actions: string[];
}

/** Writable subset. The favicon and uploaded fonts go through their own endpoints. */
export interface OrganizationSettingsUpdate {
  display?: DisplaySettings;
  branding?: {
    primary_color?: string | null;
    secondary_color?: string | null;
    product_name?: string | null;
    /** A Google family, or null to clear. Uploads go through their own endpoint. */
    font?: BrandingGoogleFont | null;
  };
}

export interface Organization {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  website?: string;
  logo_url?: string;
  email?: string;
  phone?: string;
  address?: string;
  is_active?: boolean;
  max_users?: number;
  subscription_ends_at?: string;
  domain?: string;
  is_domain_verified?: boolean;
  createdAt: string;
  owner_id: UUID;
  user_id: UUID;
  /** Read-only. Writes go through the /organizations/settings endpoints. */
  organization_settings?: OrganizationSettings | null;
}
