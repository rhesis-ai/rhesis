import { BaseApiClient } from './base-client';

export interface UsageResourceItem {
  used: number;
  limit: number | null;
  period_start: string;
  period_end: string;
  /**
   * "flow" (cumulative counter, resets each billing period) or "stock"
   * (live entity count). Comes from the API rather than a hardcoded
   * frontend list so the two can never drift apart.
   */
  kind: 'flow' | 'stock';
}

export interface UsageResponse {
  resources: Record<string, UsageResourceItem>;
  edition: string;
}

/**
 * Client for the `/usage` endpoint. Returns per-resource usage counters,
 * limits, and the current billing period for the current user's organization.
 */
export class UsageClient extends BaseApiClient {
  async getUsage(): Promise<UsageResponse> {
    return this.fetch<UsageResponse>('/usage', {
      cache: 'no-store',
    });
  }
}
