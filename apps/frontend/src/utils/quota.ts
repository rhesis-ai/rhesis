/**
 * Shared quota classification and copy. The single place that turns a
 * `UsageResourceItem` (or a 402 body) into "which zone is this in" and
 * "what does the org see about it" -- every surface (banner, brand-row
 * badge, org-menu block, usage page, inline gates) reads from here rather
 * than re-deriving its own thresholds or strings.
 */

import {
  QUOTA_RESOURCE_LABELS,
  WARNING_THRESHOLD,
  type QuotaResource,
} from '@/constants/quota';
import type { ApiErrorData } from '@/utils/api-client/base-client';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';

const COMMUNITY_EDITION = 'community';

export function isCommunityEdition(edition: string): boolean {
  return edition.toLowerCase() === COMMUNITY_EDITION;
}

/** Narrows a wire-value string (e.g. `parseQuotaError(err).resource`) to
 * `QuotaResource`. A 402 body's `resource` is always one, but it arrives
 * typed as plain `string`, and the backend can add a new `QuotaResource`
 * before `constants/quota.ts` catches up -- callers must check this before
 * indexing `QUOTA_RESOURCE_LABELS` or building a `QuotaNotice`. */
export function isKnownQuotaResource(
  resource: string
): resource is QuotaResource {
  return resource in QUOTA_RESOURCE_LABELS;
}

/**
 * The four states a metered resource can be in. Every surface that shows
 * or gates on quota classifies into exactly one of these -- see
 * `IMPLEMENTATION_PROMPT.md`'s "Four zones, not two" for the behaviour each
 * one implies.
 *
 * - `healthy`: comfortably under the warning threshold.
 * - `approaching`: at or above `WARNING_THRESHOLD` of `limit`, nothing
 *   disabled.
 * - `pastIncluded`: at or past `limit` but still under `ceiling` -- the
 *   soft-tier grace band. Still nothing disabled. Zero-width on a hard
 *   tier, where `ceiling === limit`.
 * - `blocked`: at or past `ceiling`. The action this resource gates is
 *   disabled and a 402 is what the backend returns for it.
 */
export type QuotaZone = 'healthy' | 'approaching' | 'pastIncluded' | 'blocked';

type ZoneInput = Pick<UsageResourceItem, 'used' | 'limit' | 'ceiling'>;

/**
 * Classify one resource's usage into a `QuotaZone`.
 *
 * `limit === null` (unlimited) always classifies `healthy` -- there is no
 * ratio to compute and nothing ever blocks. `limit === 0` is a real
 * configured value ("none allowed"), not a missing limit, so it reports as
 * fully consumed via the `ratio = 1` fallback rather than being treated as
 * unlimited.
 */
/** The MUI severity color a zone maps to, everywhere a zone needs one:
 * the usage-page meter, the org-menu usage rows. `healthy` is `'success'`
 * even though nothing renders it in most callers (a healthy row is
 * usually just not shown) -- kept total so a caller never has to handle
 * an `undefined` case. */
export function zoneColor(zone: QuotaZone): 'success' | 'warning' | 'error' {
  if (zone === 'blocked') return 'error';
  if (zone === 'approaching' || zone === 'pastIncluded') return 'warning';
  return 'success';
}

export function classifyZone(item: ZoneInput): QuotaZone {
  const { used, limit, ceiling } = item;
  if (limit === null) return 'healthy';
  if (ceiling !== null && used >= ceiling) return 'blocked';
  if (used >= limit) return 'pastIncluded';
  const ratio = limit === 0 ? 1 : used / limit;
  if (ratio >= WARNING_THRESHOLD) return 'approaching';
  return 'healthy';
}

/**
 * How many resources are at `approaching` or worse, skipping any resource
 * `constants/quota.ts` has no label for yet -- the backend can add a
 * `QuotaResource` before the frontend catches up, and every consumer of
 * this count (the brand-row badge, the org-menu block) must agree on how
 * many rows that implies.
 */
export function countFlagged(
  resources: Readonly<Record<string, ZoneInput>>
): number {
  let count = 0;
  for (const [resource, item] of Object.entries(resources)) {
    if (!(resource in QUOTA_RESOURCE_LABELS)) continue;
    if (classifyZone(item) !== 'healthy') count += 1;
  }
  return count;
}

export interface FlaggedResource {
  resource: QuotaResource;
  item: UsageResourceItem;
  zone: QuotaZone;
  ratio: number;
}

/**
 * Every resource at `approaching` or worse, worst-ratio first. `ratio` is
 * `used / limit`, clamped to 1 for a fully-consumed `limit: 0` resource.
 * Unlabelled resources are skipped -- see `countFlagged`.
 */
export function flaggedResources(
  resources: Readonly<Record<string, UsageResourceItem>>
): FlaggedResource[] {
  const flagged: FlaggedResource[] = [];
  for (const [resource, item] of Object.entries(resources)) {
    if (!(resource in QUOTA_RESOURCE_LABELS)) continue;
    const zone = classifyZone(item);
    if (zone === 'healthy') continue;
    const ratio =
      item.limit === null ? 0 : item.limit === 0 ? 1 : item.used / item.limit;
    flagged.push({ resource: resource as QuotaResource, item, zone, ratio });
  }
  return flagged.sort((a, b) => b.ratio - a.ratio);
}

/** The single worst flagged resource, or `null` if none is flagged. */
export function findWorstResource(
  resources: Readonly<Record<string, UsageResourceItem>>
): FlaggedResource | null {
  return flaggedResources(resources)[0] ?? null;
}

/** `"1 Sep"` -- the short form used in reset-date recourse copy. Stays in
 * UTC like `UsageOverviewTab`'s `formatPeriodDate`: `period_end` is a
 * date-only string computed in UTC, so formatting in the viewer's local
 * zone risks rolling it back a day west of UTC. */
function formatResetDate(isoDate: string): string {
  const date = new Date(isoDate);
  const day = date.getUTCDate();
  const month = date.toLocaleDateString('en-US', {
    month: 'short',
    timeZone: 'UTC',
  });
  return `${day} ${month}`;
}

/** What an admin is told to do about a blocked stock resource. Resource-
 * specific because "delete a project" and "remove a member" are different
 * actions -- a generic "free up capacity" has no next step to click. */
const STOCK_RECOURSE_ACTION: Partial<Record<QuotaResource, string>> = {
  projects: 'Delete a project',
  endpoints: 'Delete an endpoint',
  seats: 'Remove a member',
};

export interface QuotaCopyInput {
  resource: QuotaResource;
  /** `undefined` only for a 402 issued before the backend widened the
   * body (see `IMPLEMENTATION_PROMPT.md` step 1) -- falls back to the
   * `unknown` catalog row. */
  kind: 'flow' | 'stock' | undefined;
  used: number;
  limit: number;
  zone: Exclude<QuotaZone, 'healthy'>;
  /** ISO date the current period ends. Required for the `blocked`+`flow`
   * row, which names the reset date; unused otherwise. */
  periodEnd?: string;
  /** Whether this reader can act on an upgrade -- an org admin. A member
   * gets pointed at an admin instead, never at the upgrade link. */
  canUpgrade: boolean;
}

export interface QuotaCopyResult {
  sentence: string;
  recourse: string;
}

/**
 * The copy catalog, as code. One sentence + one recourse per
 * (zone, kind, audience) combination -- see `IMPLEMENTATION_PROMPT.md`'s
 * "Copy catalog" table, which this mirrors exactly. Nowhere else in the
 * app should hand-write quota sentences.
 */
export function quotaCopy({
  resource,
  kind,
  used,
  limit,
  zone,
  periodEnd,
  canUpgrade,
}: QuotaCopyInput): QuotaCopyResult {
  const label = QUOTA_RESOURCE_LABELS[resource].toLowerCase();
  const countSuffix = `(${used.toLocaleString()} of ${limit.toLocaleString()})`;

  if (zone === 'approaching') {
    const percent = Math.round((used / limit) * 100);
    return {
      sentence:
        kind === 'stock'
          ? `Your organization is using ${used.toLocaleString()} of ${limit.toLocaleString()} ${label}.`
          : `Your organization has used ${percent}% of its ${label} for this period.`,
      recourse: 'View usage · Upgrade plan →',
    };
  }

  if (zone === 'pastIncluded') {
    return {
      sentence:
        kind === 'stock'
          ? `Your organization is past its included ${label}.`
          : `Your organization is past its included ${label} for this period.`,
      recourse:
        kind === 'stock'
          ? 'You can still add more until the overage allowance runs out.'
          : 'You can keep running until the overage allowance runs out.',
    };
  }

  // zone === 'blocked'
  if (kind === undefined) {
    return {
      sentence: `Your organization has reached its ${label} limit ${countSuffix}.`,
      recourse: canUpgrade ? '' : 'Ask an org admin to raise this limit.',
    };
  }

  if (kind === 'flow') {
    const reset = periodEnd ? formatResetDate(periodEnd) : 'soon';
    return {
      sentence: `Your organization is at its ${label} limit for this period ${countSuffix}.`,
      recourse: canUpgrade
        ? `Resets ${reset}. Upgrade to raise this limit.`
        : `Resets ${reset}. Ask an org admin to raise this limit.`,
    };
  }

  const action = STOCK_RECOURSE_ACTION[resource] ?? `Free up ${label}`;
  return {
    sentence: `Your organization is at its ${label} limit ${countSuffix}.`,
    recourse: canUpgrade
      ? `${action} or upgrade to add more.`
      : `${action}, or ask an org admin to raise this limit.`,
  };
}

export interface QuotaError {
  resource: string;
  used: number;
  limit: number | null;
  kind: 'flow' | 'stock' | undefined;
  periodEnd: string | undefined;
  message: string;
}

/**
 * Read a quota-exceeded 402 back out of a caught error, or `null` if it
 * isn't one. Guards on the `quota_exceeded` marker (not just `status ===
 * 402`) -- `quota_exceeded` is the only 402 producer today, but a future
 * one shouldn't silently get parsed as a quota error.
 */
export function parseQuotaError(err: unknown): QuotaError | null {
  if (!(err instanceof Error)) return null;
  const withMeta = err as Error & { status?: number; data?: ApiErrorData };
  if (withMeta.status !== 402) return null;
  const data = withMeta.data;
  if (!data || data.error !== 'quota_exceeded' || !data.resource) return null;
  return {
    resource: data.resource,
    used: typeof data.used === 'number' ? data.used : 0,
    limit: data.limit ?? null,
    kind: data.kind,
    periodEnd: data.period_end,
    message: typeof data.message === 'string' ? data.message : '',
  };
}
