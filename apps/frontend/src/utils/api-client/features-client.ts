import { BaseApiClient } from './base-client';

export interface LicenseInfo {
  edition: string;
  licensed: boolean;
  /**
   * Whether `edition` is a paid tier. Describes the tier, not the licence
   * state, so a lapsed paid licence is `is_paid: true` with `licensed: false`.
   *
   * Never infer this from `edition` — a name comparison like
   * `edition !== 'community'` misreads any tier added or renamed later.
   * Optional only to tolerate a backend predating this field; treat a missing
   * value as "unknown", not as "free".
   *
   * To *display* a plan, use `usePlan()` with `PlanBadge` rather than building
   * anything off these fields. See `@/utils/plan`.
   */
  is_paid?: boolean;
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

export interface FeaturesResponse {
  license: LicenseInfo;
  /**
   * The org's plan, ready to render via `PlanBadge`. Read it with `usePlan()`.
   *
   * It rides on this response rather than `GET /usage` for one reason: this one
   * is server-seeded in the protected layout, so the plan is available on first
   * paint. Fetching it client-side left the sidebar's plan row blank for a round
   * trip on every cold load. Optional to tolerate a backend predating it.
   */
  plan?: Plan;
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
