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

/** Whether *edition* names the free tier. Answers "what plan is this", which
 * is a display question -- for "should this org be offered an upgrade", use
 * {@link isUnlicensedPlan}: a lapsed paid plan is not the community edition
 * but is held to community limits. */
export function isCommunityEdition(edition: string): boolean {
  return edition.toLowerCase() === COMMUNITY_EDITION;
}

/**
 * Whether the org has no active paid license, and should therefore be shown
 * an upgrade path.
 *
 * This is the question every upgrade affordance is really asking, and it is
 * deliberately *not* `isCommunityEdition(edition)`, which is what it used to
 * be. The backend reports edition and licence status separately, because a
 * lapsed licence keeps its edition name so the UI can say which one expired:
 * a canceled enterprise licence resolves to community *limits* while still
 * reporting `edition: "enterprise"`.
 *
 * Gating on the edition string stranded exactly that org. It gets free-tier
 * ceilings and 402s at 500 test runs, but does not look like a free org, so
 * every upgrade link, banner CTA and `canUpgrade` recourse line was withheld
 * -- the one state where the reader most needs to be told what to do.
 *
 * Requires a positive `licensed === false`, so anything unknown -- a loading
 * provider (`null`), or a response from a backend predating the field
 * (`undefined`) -- reads as "no opinion" and shows nothing, rather than
 * flashing an upgrade prompt at a paying customer.
 */
export function isUnlicensedPlan(
  edition: string | null,
  licensed: boolean | null | undefined
): boolean {
  if (edition === null) return false;
  return licensed === false;
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

/**
 * Classify one resource's usage into a `QuotaZone`.
 *
 * `limit === null` (unlimited) always classifies `healthy`: nothing to
 * measure against and nothing ever blocks.
 *
 * `limit === 0` is a real configured value ("none allowed"), not a missing
 * limit. It classifies `blocked`, because the backend's own rule is
 * `allowed = used < ceiling` and `ceiling_for(0)` is `0` -- so such an org
 * is refused from its very first request, and the UI must agree.
 *
 * A null `ceiling` alongside a numeric `limit` is not something the API
 * emits (`ceiling_for` returns null only for a null limit), but it is
 * treated as a hard tier rather than ignored: leaving it unhandled would
 * park the resource in `pastIncluded` forever and promise an overage
 * allowance that does not exist.
 */
export function classifyZone(item: ZoneInput): QuotaZone {
  const { used, limit, ceiling } = item;
  if (limit === null) return 'healthy';
  if (used >= (ceiling ?? limit)) return 'blocked';
  if (used >= limit) return 'pastIncluded';
  if (used / limit >= WARNING_THRESHOLD) return 'approaching';
  return 'healthy';
}

export interface FlaggedResource {
  resource: QuotaResource;
  item: UsageResourceItem;
  /** Never `healthy` -- `flaggedResources` filters those out, and saying so
   * in the type means callers can build copy from it without re-checking. */
  zone: Exclude<QuotaZone, 'healthy'>;
  ratio: number;
}

/** Severity order for sorting. Higher is worse. */
const ZONE_SEVERITY: Record<QuotaZone, number> = {
  healthy: 0,
  approaching: 1,
  pastIncluded: 2,
  blocked: 3,
};

/**
 * Every resource at `approaching` or worse, worst first: by zone severity,
 * then by ratio within a zone.
 *
 * Zone before ratio, not ratio alone. Ratio is measured against `limit`, so
 * a soft-tier resource deep in its grace band (150/100, ratio 1.5, still
 * running) outranks a hard-blocked one (1/1, ratio 1.0) on ratio -- and
 * since `QuotaBanner` shows only the single worst resource, sorting by
 * ratio alone hid an actual block behind a warning.
 *
 * `ratio` is `used / limit`, clamped to 1 for a fully-consumed `limit: 0`
 * resource. Unlabelled resources are skipped: the backend can add a
 * `QuotaResource` before `constants/quota.ts` catches up, and these render
 * in the protected layout where a missing label would throw on every page.
 */
export function flaggedResources(
  resources: Readonly<Record<string, UsageResourceItem>>
): FlaggedResource[] {
  const flagged: FlaggedResource[] = [];
  for (const [resource, item] of Object.entries(resources)) {
    if (!(resource in QUOTA_RESOURCE_LABELS)) continue;
    const zone = classifyZone(item);
    if (zone === 'healthy') continue;
    // Narrowed by the guard above; `classifyZone` returns the wider union.
    const ratio =
      item.limit === null ? 0 : item.limit === 0 ? 1 : item.used / item.limit;
    flagged.push({ resource: resource as QuotaResource, item, zone, ratio });
  }
  return flagged.sort(
    (a, b) => ZONE_SEVERITY[b.zone] - ZONE_SEVERITY[a.zone] || b.ratio - a.ratio
  );
}

/** The single worst flagged resource, or `null` if none is flagged. */
export function findWorstResource(
  resources: Readonly<Record<string, UsageResourceItem>>
): FlaggedResource | null {
  return flaggedResources(resources)[0] ?? null;
}

export interface UsageRow {
  resource: QuotaResource;
  item: UsageResourceItem;
  /** Unlike `FlaggedResource`, may be `healthy`: the list is padded with
   * resources that are perfectly fine. */
  zone: QuotaZone;
}

/**
 * Flagged resources first (worst first), then padded with the next resources
 * in canonical order up to `minRows`.
 *
 * A floor, never a cap: every flagged resource gets a row, so the row count
 * always agrees with the badge that summarises it. The padding exists only so
 * the block does not read as near-empty for a healthy org.
 *
 * Skips unlimited resources when padding: "Model Tokens unlimited" is a row
 * that tells the reader nothing.
 */
export function usageMenuRows(
  resources: Readonly<Record<string, UsageResourceItem>>,
  order: readonly QuotaResource[],
  minRows: number
): UsageRow[] {
  const rows: UsageRow[] = flaggedResources(resources).map(
    ({ resource, item, zone }) => ({ resource, item, zone })
  );
  if (rows.length >= minRows) return rows;

  const included = new Set(rows.map(row => row.resource));
  for (const resource of order) {
    if (rows.length >= minRows) break;
    if (included.has(resource)) continue;
    const item = resources[resource];
    if (!item || item.limit === null) continue;
    rows.push({ resource, item, zone: classifyZone(item) });
  }
  return rows;
}

/**
 * How much of a usage row's progress bar is filled, as a whole-number
 * percent -- how close the resource is to `limit` (not `ceiling`): the bar
 * answers the same question the row's trailing value does, a percent or a
 * count of `limit`.
 *
 * Capped at 100 -- an over-limit soft-tier row (`used > limit`) still draws
 * a full bar, not one that overflows its track. Fully filled, not zero,
 * when there is no real `limit` to divide by: `limit: 0` ("none allowed")
 * always classifies `blocked` (see `classifyZone`), even at `used: 0`, so
 * an empty-looking bar there would contradict its own red fill colour.
 */
export function usageRowFillPercent(item: ZoneInput): number {
  if (!item.limit) return 100;
  return Math.min(100, Math.round((item.used / item.limit) * 100));
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
      // No prose recourse: nothing is blocked yet, and the two affordances
      // that belong here ("View usage", "Upgrade plan") are links, which
      // every surface renders itself rather than taking as a string.
      recourse: '',
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
    // Safety net for a 402 issued before the backend widened its body. With
    // no `kind` there is neither a reset date nor a "delete one" action to
    // name, so the recourse is only about who can raise the limit.
    return {
      sentence: `Your organization is at its ${label} limit ${countSuffix}.`,
      recourse: canUpgrade
        ? 'Upgrade to raise this limit.'
        : 'Ask an org admin to raise this limit.',
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
