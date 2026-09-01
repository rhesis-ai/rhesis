import { BaseApiClient } from './base-client';

export interface UsageResourceItem {
  used: number;
  limit: number | null;
  /**
   * The value of `used` at which requests actually start failing: `limit`
   * plus the tier's overage tolerance on a soft policy, `limit` itself on a
   * hard one. Compare against this, not `limit`, to predict a 402 -- gating
   * on `limit` disables actions for a paying org that still has its whole
   * grace band left. `limit` is what a progress bar fills toward.
   */
  ceiling: number | null;
  period_start: string;
  period_end: string;
  /**
   * "flow" (cumulative counter, resets each billing period) or "stock"
   * (live entity count). Comes from the API rather than a hardcoded
   * frontend list so the two can never drift apart.
   */
  kind: 'flow' | 'stock';
}

/**
 * The org's plan, as the API describes it.
 *
 * Deliberately not a union of known tiers. `name` is a display string to be
 * rendered verbatim, and styling comes from the two booleans — so a renamed or
 * newly added tier needs no frontend change. See `utils/plan.ts`.
 */
export interface Plan {
  /**
   * Display label. **Render verbatim.** Do not case, map, translate or append
   * to it — the API composes the whole thing, including the qualifier a lapsed
   * paid plan carries.
   */
  name: string;
  /**
   * Whether this is a paid tier. Describes the *tier*, not the licence, so a
   * canceled enterprise licence is still `true`.
   */
  is_paid: boolean;
  /**
   * Whether the licence is currently active. Together with `is_paid` this
   * separates a free org `(false, false)` from a lapsed paid one
   * `(true, false)` — the distinction that decides both badge styling and
   * whether an upgrade path is offered.
   */
  is_active: boolean;
}

export interface UsageResponse {
  resources: Record<string, UsageResourceItem>;
  /**
   * Machine identifier for the licence edition. Diagnostics only — never for
   * display, and never for deciding styling. Use `plan`.
   */
  edition: string;
  plan: Plan;
}

export interface UsageHistoryPoint {
  period_start: string;
  used: number;
}

export interface UsageHistoryResponse {
  /**
   * Flow resources only -- stock resources (seats/projects/endpoints) are
   * live counts with no historical row to report, so they're absent here
   * rather than repeating today's count at every point.
   */
  resources: Record<string, UsageHistoryPoint[]>;
}

/**
 * Client for the `/usage` endpoints. Returns per-resource usage counters,
 * limits, and the current billing period for the current user's organization.
 */
export class UsageClient extends BaseApiClient {
  /**
   * @param periodStart First day of the month to report (`YYYY-MM-DD`).
   * Omit for the current billing period.
   */
  async getUsage(periodStart?: string): Promise<UsageResponse> {
    const query = periodStart ? `?period=${periodStart}` : '';
    return this.fetch<UsageResponse>(`/usage${query}`, {
      cache: 'no-store',
    });
  }

  async getUsageHistory(months: number): Promise<UsageHistoryResponse> {
    return this.fetch<UsageHistoryResponse>(`/usage/history?months=${months}`, {
      cache: 'no-store',
    });
  }
}
