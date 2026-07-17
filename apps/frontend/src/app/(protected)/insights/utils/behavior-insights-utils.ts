import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  BehaviorPassRates,
  MetricPassRates,
  PassFailStats,
  TestResultsStats,
  TopicPassRates,
} from '@/utils/api-client/interfaces/test-results';
import {
  readInsightsEndpointId,
  writeInsightsEndpointId,
} from '@/utils/insights-endpoint';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { TestRun } from '@/utils/api-client/interfaces/test-run';
import {
  InsightsFilters,
  InsightsTimeRange,
  resolveInsightsTimeRange,
  timeRangeToStatsParams,
} from '../types';

function endpointMatchesProject(
  endpoint: Endpoint,
  projectId: string | undefined
): boolean {
  if (!projectId) return true;
  return String(endpoint.project_id) === String(projectId);
}

export interface DimensionItem {
  name: string;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
}

export interface BehaviorInsightColumn {
  id: string;
  name: string;
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

/** Sort behavior insight columns alphabetically by name (A–Z). */
export function sortBehaviorColumns(
  columns: BehaviorInsightColumn[]
): BehaviorInsightColumn[] {
  return [...columns].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  );
}

export function passRatesToItems(
  rates: MetricPassRates | TopicPassRates | BehaviorPassRates | undefined
): DimensionItem[] {
  if (!rates) return [];
  return Object.entries(rates).map(([name, stats]) => ({
    name,
    ...stats,
  }));
}

export function isBehaviorColumnExpandable(
  column: Pick<BehaviorInsightColumn, 'overall' | 'metrics' | 'topics'>
): boolean {
  return (
    column.overall.total > 0 &&
    (column.metrics.length > 0 || column.topics.length > 0)
  );
}

export const INSIGHTS_BEHAVIOR_COLUMNS_PER_ROW = 3;

export function chunkBehaviorColumns(
  columns: BehaviorInsightColumn[]
): BehaviorInsightColumn[][] {
  const rows: BehaviorInsightColumn[][] = [];
  for (let i = 0; i < columns.length; i += INSIGHTS_BEHAVIOR_COLUMNS_PER_ROW) {
    rows.push(columns.slice(i, i + INSIGHTS_BEHAVIOR_COLUMNS_PER_ROW));
  }
  return rows;
}

export function isBehaviorRowExpandable(row: BehaviorInsightColumn[]): boolean {
  return row.some(isBehaviorColumnExpandable);
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

export function resolveEndpointId(
  endpoints: Endpoint[],
  projectId: string | undefined
): string | null {
  const projectEndpoints = endpoints.filter(e =>
    endpointMatchesProject(e, projectId)
  );

  if (projectEndpoints.length === 0) return null;

  const stored = readInsightsEndpointId();
  if (stored) {
    const found = projectEndpoints.find(e => e.id === stored);
    if (found) return found.id;
  }

  const fallback = projectEndpoints[0].id;
  writeInsightsEndpointId(fallback);
  return fallback;
}

export function buildEndpointRunFilter(endpointId: string): string {
  return `test_configuration/endpoint_id eq '${endpointId}'`;
}

export async function fetchTestRunsForEndpoint(
  endpointId: string,
  timeRange?: InsightsTimeRange
): Promise<TestRun[]> {
  const client = new ApiClientFactory().getTestRunsClient();
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

export async function fetchTestRunIdsForEndpoint(
  endpointId: string,
  timeRange?: InsightsTimeRange
): Promise<string[]> {
  const runs = await fetchTestRunsForEndpoint(
    endpointId,
    timeRange
  );
  return runs.map(run => run.id);
}

/**
 * Soft cap for `test_run_ids` query params on `/test_results/stats`.
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

/** Resolve which test run IDs to query based on Insights filter state. */
export async function resolveInsightsQueryTestRunIds(
  filters: Pick<
    InsightsFilters,
    'endpointId' | 'runFilterMode' | 'timeRange' | 'testRunIds'
  >
): Promise<string[]> {
  let testRunIds: string[];

  if (filters.runFilterMode === 'timeRange') {
    testRunIds = await fetchTestRunIdsForEndpoint(
      filters.endpointId,
      resolveInsightsTimeRange(filters.timeRange)
    );
  } else if (filters.testRunIds.length > 0) {
    testRunIds = filters.testRunIds;
  } else {
    testRunIds = await fetchTestRunIdsForEndpoint(
      filters.endpointId
    );
  }

  assertInsightsTestRunIdsWithinLimit(testRunIds);
  return testRunIds;
}

export function buildBehaviorColumns(
  behaviorsWithData: Array<{ id: string; name: string }>,
  behaviorPassRates: BehaviorPassRates,
  perBehaviorResults: TestResultsStats[]
): BehaviorInsightColumn[] {
  const columns: BehaviorInsightColumn[] = perBehaviorResults.map(
    (result, index) => {
      const behavior = behaviorsWithData[index];
      const name = behavior?.name ?? '';
      const overall = result.overall_pass_rates ??
        behaviorPassRates[name] ?? {
          total: 0,
          passed: 0,
          failed: 0,
          pass_rate: 0,
        };

      return {
        id: behavior?.id ?? name,
        name,
        overall,
        metrics: sortByPassRateAsc(passRatesToItems(result.metric_pass_rates)),
        topics: sortByPassRateAsc(passRatesToItems(result.topic_pass_rates)),
      };
    }
  );

  return sortBehaviorColumns(columns);
}
