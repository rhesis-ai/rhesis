import { FeatureName } from '@/constants/features';
import { BaseApiClient } from './base-client';

export interface LicenseInfo {
  edition: string;
  licensed: boolean;
}

export interface FeaturesResponse {
  license: LicenseInfo;
  enabled: FeatureName[];
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
