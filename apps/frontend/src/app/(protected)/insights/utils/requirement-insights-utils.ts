import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PassFailStats } from '@/utils/api-client/interfaces/test-results';
import { InsightsRow } from '@/utils/api-client/interfaces/insights';
import {
  readInsightsEndpointId,
  writeInsightsEndpointId,
} from '@/utils/insights-endpoint';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { TestRun } from '@/utils/api-client/interfaces/test-run';
import {
  DEFAULT_INSIGHTS_GROUP_BY,
  INSIGHTS_NONE_GROUP_LABELS,
  InsightsFilters,
  InsightsGroupBy,
  InsightsTimeRange,
  resolveInsightsTimeRange,
  timeRangeToStatsParams,
} from '../types';

/** The registry dimension (and its `<dimension>_id` key) behind each group-by. */
export const INSIGHTS_GROUP_DIMENSIONS: Record<
  InsightsGroupBy,
  { dimension: string; idKey: string }
> = {
  requirement: { dimension: 'requirement', idKey: 'requirement_id' },
  impact: { dimension: 'impact', idKey: 'impact_id' },
  parent: { dimension: 'requirement_parent', idKey: 'requirement_parent_id' },
};

function endpointMatchesProject(
  endpoint: Endpoint,
  projectId: string | undefined
): boolean {
  if (!projectId) return true;
  return String(endpoint.project_id) === String(projectId);
}

export interface DimensionItem {
  name: string;
  /** Present for dimensions that group by id (e.g. topics via topic_id). */
  id?: string;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
}

/**
 * One column on the Insights page: a requirement, an impact or a parent
 * requirement, depending on `groupBy`. `id` is null for the group of
 * requirements that have no impact or no parent -- it still counts, it just
 * can't be drilled into by id.
 */
export interface RequirementInsightColumn {
  id: string | null;
  name: string;
  groupBy: InsightsGroupBy;
  /** The impact name behind the column's dot: the requirement's own, or the impact itself. */
  impact: string | null;
  /** Grouped by impact or parent: the requirements in the group, A–Z. Empty by requirement. */
  children: string[];
  overall: PassFailStats;
  metrics: DimensionItem[];
  topics: DimensionItem[];
}

/** Sort ascending by pass rate (worst first), with zero-test items last. */
export function sortByPassRateAsc<
  T extends { pass_rate: number; total: number },
>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const aEmpty = a.total === 0;
    const bEmpty = b.total === 0;
    if (aEmpty !== bEmpty) return aEmpty ? 1 : -1;
    return a.pass_rate - b.pass_rate;
  });
}

/** Sort requirement insight columns alphabetically by name (A–Z), the "none" group last. */
export function sortRequirementColumns(
  columns: RequirementInsightColumn[]
): RequirementInsightColumn[] {
  return [...columns].sort((a, b) => {
    if ((a.id === null) !== (b.id === null)) return a.id === null ? 1 : -1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  });
}

/**
 * One `/insights/query` row -> the `PassFailStats` shape used across the Insights UI.
 * `total` is `passed + failed`, not the row's raw `count` -- `count` also includes
 * pending/errored results that never got evaluated, which would make "X/Y passed"
 * text count them in the denominator without them showing up as either passed or failed.
 */
export function rowToPassFailStats(row: InsightsRow): PassFailStats {
  const passed = Number(row.passed ?? 0);
  const failed = Number(row.failed ?? 0);
  return {
    total: passed + failed,
    passed,
    failed,
    pass_rate: Number(row.pass_rate ?? 0),
  };
}

export function isRequirementColumnExpandable(
  column: Pick<RequirementInsightColumn, 'overall' | 'metrics' | 'topics'>
): boolean {
  return (
    column.overall.total > 0 &&
    (column.metrics.length > 0 || column.topics.length > 0)
  );
}

export const INSIGHTS_REQUIREMENT_COLUMNS_PER_ROW = 3;

export function chunkRequirementColumns(
  columns: RequirementInsightColumn[]
): RequirementInsightColumn[][] {
  const rows: RequirementInsightColumn[][] = [];
  for (
    let i = 0;
    i < columns.length;
    i += INSIGHTS_REQUIREMENT_COLUMNS_PER_ROW
  ) {
    rows.push(columns.slice(i, i + INSIGHTS_REQUIREMENT_COLUMNS_PER_ROW));
  }
  return rows;
}

export function isRequirementRowExpandable(
  row: RequirementInsightColumn[]
): boolean {
  return row.some(isRequirementColumnExpandable);
}

export function buildTestRunTimeFilter(timeRange: InsightsTimeRange): string {
  const params = timeRangeToStatsParams(timeRange);
  if (params.start_date) {
    return `created_at ge '${params.start_date}'`;
  }
  if (params.months) {
    const end = new Date();
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 30 * params.months);
    return `created_at ge '${start.toISOString()}'`;
  }
  return '';
}

/**
 * Pure endpoint pick shared by the client (`resolveEndpointId`) and the
 * server prefetch: the remembered `storedId` if it belongs to the project,
 * else the project's first endpoint.
 */
export function pickEndpointId(
  endpoints: Endpoint[],
  projectId: string | undefined,
  storedId: string | null
): string | null {
  const projectEndpoints = endpoints.filter(e =>
    endpointMatchesProject(e, projectId)
  );

  if (projectEndpoints.length === 0) return null;

  if (storedId && projectEndpoints.some(e => e.id === storedId)) {
    return storedId;
  }

  return projectEndpoints[0].id;
}

export function resolveEndpointId(
  endpoints: Endpoint[],
  projectId: string | undefined
): string | null {
  const stored = readInsightsEndpointId();
  const resolved = pickEndpointId(endpoints, projectId, stored);
  if (resolved && resolved !== stored) {
    writeInsightsEndpointId(resolved);
  }
  return resolved;
}

export function buildEndpointRunFilter(endpointId: string): string {
  return `test_configuration/endpoint_id eq '${endpointId}'`;
}

export async function fetchTestRunsForEndpoint(
  endpointId: string,
  timeRange?: InsightsTimeRange,
  factory: ApiClientFactory = new ApiClientFactory()
): Promise<TestRun[]> {
  const client = factory.getTestRunsClient();
  const filterParts = [buildEndpointRunFilter(endpointId)];
  if (timeRange) {
    const timeFilter = buildTestRunTimeFilter(timeRange);
    if (timeFilter) {
      filterParts.push(timeFilter);
    }
  }
  const filter = filterParts.join(' and ');
  const runs: TestRun[] = [];
  let skip = 0;
  const limit = 100;

  while (true) {
    const response = await client.getTestRuns({
      filter,
      skip,
      limit,
      sort_by: 'created_at',
      sort_order: 'desc',
    });

    runs.push(...response.data);
    // Prefer page-size termination over totalCount — some responses omit
    // x-total-count and totalCount defaults to 0, which would stop after
    // the first page and silently drop later runs.
    if (response.data.length < limit) {
      break;
    }
    skip += limit;
  }

  return runs;
}

/** The ids among `endpointIds` with at least one test run in `timeRange`. */
export async function findEndpointIdsWithRuns(
  endpointIds: string[],
  timeRange?: InsightsTimeRange,
  factory: ApiClientFactory = new ApiClientFactory()
): Promise<string[]> {
  const client = factory.getTestRunsClient();
  const timeFilter = timeRange ? buildTestRunTimeFilter(timeRange) : '';
  const hasRuns = await Promise.all(
    endpointIds.map(async id => {
      const filter = [buildEndpointRunFilter(id), timeFilter]
        .filter(Boolean)
        .join(' and ');
      const response = await client.getTestRuns({ filter, skip: 0, limit: 1 });
      return response.data.length > 0;
    })
  );
  return endpointIds.filter((_id, i) => hasRuns[i]);
}

export async function fetchTestRunIdsForEndpoint(
  endpointId: string,
  timeRange?: InsightsTimeRange,
  factory?: ApiClientFactory
): Promise<string[]> {
  const runs = await fetchTestRunsForEndpoint(endpointId, timeRange, factory);
  return runs.map(run => run.id);
}

/**
 * Soft cap for `test_run_ids` query params on Insights endpoints.
 * Beyond this, GET URLs risk proxy/browser length limits.
 */
export const MAX_INSIGHTS_TEST_RUN_IDS = 100;

export function assertInsightsTestRunIdsWithinLimit(
  testRunIds: string[]
): void {
  if (testRunIds.length > MAX_INSIGHTS_TEST_RUN_IDS) {
    throw new Error(
      `Too many test runs to query at once (${testRunIds.length}; max ${MAX_INSIGHTS_TEST_RUN_IDS}). Narrow your selection or use a shorter time range.`
    );
  }
}

/**
 * Resolve which test run IDs to query based on Insights filter state.
 * `factory` is only passed by the server prefetch; client callers use the
 * default no-arg factory (BFF proxy).
 */
export async function resolveInsightsQueryTestRunIds(
  filters: Pick<
    InsightsFilters,
    'endpointId' | 'runFilterMode' | 'timeRange' | 'testRunIds'
  >,
  factory?: ApiClientFactory
): Promise<string[]> {
  let testRunIds: string[];

  if (filters.runFilterMode === 'timeRange') {
    testRunIds = await fetchTestRunIdsForEndpoint(
      filters.endpointId,
      resolveInsightsTimeRange(filters.timeRange),
      factory
    );
  } else if (filters.testRunIds.length > 0) {
    testRunIds = filters.testRunIds;
  } else {
    testRunIds = await fetchTestRunIdsForEndpoint(
      filters.endpointId,
      undefined,
      factory
    );
  }

  assertInsightsTestRunIdsWithinLimit(testRunIds);
  return testRunIds;
}

/** Map key for a group id; the null group (no impact / no parent) gets its own. */
const NONE_GROUP_KEY = '\u0000none';

function groupKey(id: unknown): string | undefined {
  if (typeof id === 'string') return id;
  return id === null ? NONE_GROUP_KEY : undefined;
}

/** Group rows sharing a group id (`groupIdKey`) into `DimensionItem[]`, keyed by `nameKey`. */
function groupRowsByGroupId(
  rows: InsightsRow[],
  groupIdKey: string,
  nameKey: string,
  idKey?: string
): Map<string, DimensionItem[]> {
  const grouped = new Map<string, DimensionItem[]>();
  for (const row of rows) {
    const key = groupKey(row[groupIdKey]);
    const name = row[nameKey];
    if (key === undefined || typeof name !== 'string') continue;
    const id = idKey != null ? row[idKey] : undefined;
    const items = grouped.get(key) ?? [];
    items.push({
      name,
      ...(typeof id === 'string' ? { id } : {}),
      ...rowToPassFailStats(row),
    });
    grouped.set(key, items);
  }
  return grouped;
}

/**
 * Build requirement columns straight from `/insights/query` rows: `requirementRows`
 * (group_by=[requirement], which returns requirement and requirement_id) already are "requirements with data" -- no
 * separate requirement list fetch needed. `topicRows`/`metricRows` are grouped
 * by requirement_id to fill each column's breakdown lists.
 */
export interface RequirementOption {
  id: string;
  name: string;
  count: number;
}

/** Build the full (unfiltered) requirement list for the filter drawer's checkbox options. */
export function buildRequirementOptions(
  rows: InsightsRow[]
): RequirementOption[] {
  return rows
    .filter(
      (
        row
      ): row is InsightsRow & { requirement_id: string; requirement: string } =>
        typeof row.requirement_id === 'string' &&
        typeof row.requirement === 'string'
    )
    .map(row => ({
      id: row.requirement_id,
      name: row.requirement,
      count: rowToPassFailStats(row).total,
    }))
    .sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
    );
}

/**
 * One column per group row. Grouped by requirement, a row without one is
 * skipped as before; grouped by impact or parent, the null row becomes the
 * "No impact" / "No parent" column so those requirements are never dropped.
 */
export function buildRequirementColumns(
  groupRows: InsightsRow[],
  topicRows: InsightsRow[],
  metricRows: InsightsRow[],
  groupBy: InsightsGroupBy = DEFAULT_INSIGHTS_GROUP_BY,
  childRows: InsightsRow[] = []
): RequirementInsightColumn[] {
  const { dimension, idKey } = INSIGHTS_GROUP_DIMENSIONS[groupBy];
  const topicsByGroup = groupRowsByGroupId(
    topicRows,
    idKey,
    'topic',
    'topic_id'
  );
  const metricsByGroup = groupRowsByGroupId(metricRows, idKey, 'metric');
  const childrenByGroup = groupRowsByGroupId(childRows, idKey, 'requirement');

  const columns: RequirementInsightColumn[] = [];
  for (const row of groupRows) {
    const key = groupKey(row[idKey]);
    if (key === undefined) continue;
    const isNone = key === NONE_GROUP_KEY;
    if (isNone && groupBy === 'requirement') continue;
    const name = row[dimension];
    if (!isNone && typeof name !== 'string') continue;
    const impact =
      groupBy === 'impact' ? (isNone ? null : String(name)) : row.impact;
    columns.push({
      id: isNone ? null : key,
      name: isNone ? INSIGHTS_NONE_GROUP_LABELS[groupBy] : String(name),
      groupBy,
      impact: typeof impact === 'string' ? impact : null,
      children: (childrenByGroup.get(key) ?? [])
        .map(child => child.name)
        .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' })),
      overall: rowToPassFailStats(row),
      metrics: sortByPassRateAsc(metricsByGroup.get(key) ?? []),
      topics: sortByPassRateAsc(topicsByGroup.get(key) ?? []),
    });
  }

  return sortRequirementColumns(columns);
}

export const EMPTY_INSIGHTS_SUMMARY: PassFailStats = {
  total: 0,
  passed: 0,
  failed: 0,
  pass_rate: 0,
};

/** The fetched half of `RequirementInsightsData` -- what the server prefetch seeds. */
export interface RequirementInsightsResult {
  summary: PassFailStats;
  columns: RequirementInsightColumn[];
  /** Full, unfiltered requirement list -- for the filter drawer's checkbox options. */
  requirementOptions: RequirementOption[];
  noRuns: boolean;
}

/**
 * Run the `/insights/query` batch for the given filters and already-resolved
 * test run IDs. Shared by `useRequirementInsightsData` (client) and the
 * Insights server prefetch; `factory` is only passed by the latter.
 */
export async function fetchRequirementInsights(
  filters: InsightsFilters,
  testRunIds: string[],
  factory: ApiClientFactory = new ApiClientFactory()
): Promise<RequirementInsightsResult> {
  if (testRunIds.length === 0) {
    return {
      summary: EMPTY_INSIGHTS_SUMMARY,
      columns: [],
      requirementOptions: [],
      noRuns: true,
    };
  }

  const timeParams =
    filters.runFilterMode === 'timeRange'
      ? timeRangeToStatsParams(resolveInsightsTimeRange(filters.timeRange))
      : {};
  const measures = ['passed', 'failed', 'pass_rate'];

  // `null` means "no filter" (default); `[]` means the user explicitly
  // unchecked every box -- a real, distinct state that should show zero data,
  // not silently fall back to "all". The backend can't express "match zero"
  // through an omitted filter (an empty list is dropped and treated as "no
  // restriction"), so that case is handled client-side below instead of being
  // sent as a query param.
  const showsNoData =
    (filters.requirementIds !== null && filters.requirementIds.length === 0) ||
    (filters.statusIds !== null && filters.statusIds.length === 0) ||
    (filters.impactIds !== null && filters.impactIds.length === 0);

  // Status narrows every test_result query, including the "options" scope
  // below -- unlike requirementIds, this isn't a client-side column toggle, so
  // the checkbox list itself should only offer requirements that exist within
  // the selected status.
  const testResultFilterExtras: Record<string, string[]> = {};
  if (filters.statusIds !== null && filters.statusIds.length > 0) {
    testResultFilterExtras.status_ids = filters.statusIds;
  }

  // Like requirementIds, impact narrows the columns and the summary but not
  // the drawer's requirement list (optionsQuery below).
  const requirementFilter: Record<string, string[]> = {};
  if (filters.requirementIds !== null && filters.requirementIds.length > 0) {
    requirementFilter.requirement_ids = filters.requirementIds;
  }
  if (filters.impactIds !== null && filters.impactIds.length > 0) {
    requirementFilter.impact_ids = filters.impactIds;
  }

  // The dimension each column stands for; by requirement, each row also
  // carries the requirement's impact for the dot on the column.
  const { dimension } = INSIGHTS_GROUP_DIMENSIONS[filters.groupBy];
  const groupDimensions =
    filters.groupBy === 'requirement' ? ['requirement', 'impact'] : [dimension];

  // Unfiltered by requirementIds -- used only to populate the drawer's full
  // requirement checkbox list (with counts), independent of which
  // requirements are currently checked.
  const optionsQuery = {
    filters: { test_run_ids: testRunIds, ...testResultFilterExtras },
    ...timeParams,
  };

  // Actual display/summary scope for the test_result entity -- also narrowed
  // to the checked requirements so the pass rate and columns reflect the
  // filter, not just which columns are shown.
  const testResultQuery = {
    filters: { ...optionsQuery.filters, ...requirementFilter },
    ...timeParams,
  };

  // The `metric` entity's registry filters don't include status_ids
  // (see services/insights/registry.py) -- sending it would 400.
  const metricQuery = {
    filters: { test_run_ids: testRunIds, ...requirementFilter },
    ...timeParams,
  };

  const results = await factory.getInsightsClient().getInsightsQuery({
    summary: {
      entity: 'test_result',
      group_by: [],
      measures,
      ...testResultQuery,
    },
    requirements: {
      entity: 'test_result',
      group_by: groupDimensions,
      measures,
      ...testResultQuery,
    },
    topics: {
      entity: 'test_result',
      group_by: [dimension, 'topic'],
      measures,
      ...testResultQuery,
    },
    metrics: {
      entity: 'metric',
      group_by: [dimension, 'metric'],
      measures,
      ...metricQuery,
    },
    allRequirements: {
      entity: 'test_result',
      group_by: ['requirement'],
      measures,
      ...optionsQuery,
    },
    // Grouped by impact or parent, the heading names the requirements in each group.
    ...(filters.groupBy !== 'requirement'
      ? {
          children: {
            entity: 'test_result',
            group_by: [dimension, 'requirement'],
            measures: ['count'],
            ...testResultQuery,
          },
        }
      : {}),
  });

  const requirementOptions = buildRequirementOptions(
    results.allRequirements.rows
  );

  if (showsNoData) {
    return {
      summary: EMPTY_INSIGHTS_SUMMARY,
      columns: [],
      requirementOptions,
      noRuns: false,
    };
  }

  const summaryRow = results.summary.rows[0];
  return {
    summary: summaryRow
      ? rowToPassFailStats(summaryRow)
      : EMPTY_INSIGHTS_SUMMARY,
    columns: buildRequirementColumns(
      results.requirements.rows,
      results.topics.rows,
      results.metrics.rows,
      filters.groupBy,
      results.children?.rows ?? []
    ),
    requirementOptions,
    noRuns: false,
  };
}
