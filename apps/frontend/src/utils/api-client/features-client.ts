import { BaseApiClient } from './base-client';

export interface LicenseInfo {
  edition: string;
  licensed: boolean;
}

export interface FeaturesResponse {
  license: LicenseInfo;
  /** Wire type is string[] to tolerate unknown feature names from newer backends. */
  enabled: string[];
  /** Per-feature warnings for features that are licensed but not operationally ready. */
  warnings?: Record<string, string>;
  /** Per-resource quota limits for the current org's tier. */
  limits?: Record<string, number | null>;
  /**
   * Whether this deployment runs in local/self-hosted mode. Single source of
   * truth for local-only UI -- optional to tolerate an older backend that
   * predates this field.
   */
  is_local?: boolean;
  /**
   * Whether the Rhesis platform API key option is enabled (ENABLE_RHESIS_KEY).
   * Optional to tolerate older backends that predate this field.
   */
  rhesis_key_enabled?: boolean;
}

/**
 * Client for the `/features` endpoint. Returns the license info and
 * the set of features enabled for the current user's organization.
 *
 * Unknown strings returned by the server (e.g. a newer backend with a
 * feature the frontend does not know about yet) are tolerated -- they
 * land in `enabled` but never match a call to `useFeature(FeatureName.X)`.
 */
export class FeaturesClient extends BaseApiClient {
  async getFeatures(): Promise<FeaturesResponse> {
    return this.fetch<FeaturesResponse>('/features', {
      cache: 'no-store',
    });
  }
}
