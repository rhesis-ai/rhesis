import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  InsightsFilters,
  InsightsRunFilterMode,
  InsightsTimeRange,
  resolveInsightsTimeRange,
} from '../types';
import { resolveInsightsQueryTestRunIds } from './requirement-insights-utils';

export const INSIGHTS_FAILED_TESTS_QUERY = 'failedFromInsights';
export const INSIGHTS_OUTCOME_ALL = 'all';
export const INSIGHTS_RUN_FILTER_MODE_PARAM = 'runFilterMode';
export const INSIGHTS_TIME_RANGE_PARAM = 'timeRange';
export const INSIGHTS_TEST_RUN_IDS_PARAM = 'testRunIds';

/** @deprecated Legacy URL param — parsed for backward compatibility. */
export const INSIGHTS_TEST_RUN_SCOPE_PARAM = 'testRunScope';

export type InsightsTestOutcome = 'failed' | 'all';

/**
 * The column a drill-down came from: a requirement, an impact or a parent
 * requirement. Only one of the id pairs is set at a time.
 */
export interface InsightsFailedTestsScope {
  requirementId?: string;
  requirementName?: string;
  impactId?: string;
  impactName?: string;
  requirementParentId?: string;
  requirementParentName?: string;
  metricName?: string;
  topicId?: string;
  topicName?: string;
  outcome?: InsightsTestOutcome;
}

export interface InsightsFailedTestsFilter extends InsightsFailedTestsScope {
  endpointId: string;
  runFilterMode: InsightsRunFilterMode;
  timeRange: InsightsTimeRange;
  testRunIds: string[];
}

/** The name of the column a drill-down came from, whichever kind it was. */
export function insightsScopeGroupName(
  scope: Pick<
    InsightsFailedTestsScope,
    'requirementName' | 'impactName' | 'requirementParentName'
  >
): string | undefined {
  return (
    scope.requirementName ?? scope.impactName ?? scope.requirementParentName
  );
}

export type InsightsRunContextFilters = Pick<
  InsightsFilters,
  'endpointId' | 'runFilterMode' | 'timeRange' | 'testRunIds'
>;

export function buildInsightsFailedTestsUrl(
  filters: InsightsRunContextFilters,
  scope?: InsightsFailedTestsScope
): string {
  const params = new URLSearchParams({
    [INSIGHTS_FAILED_TESTS_QUERY]: '1',
    endpointId: filters.endpointId,
    [INSIGHTS_RUN_FILTER_MODE_PARAM]: filters.runFilterMode,
  });

  if (filters.runFilterMode === 'timeRange') {
    params.set(
      INSIGHTS_TIME_RANGE_PARAM,
      resolveInsightsTimeRange(filters.timeRange)
    );
  } else if (filters.runFilterMode === 'testRuns') {
    // Explicit empty list = all runs for the endpoint (parsed the same way).
    params.set(INSIGHTS_TEST_RUN_IDS_PARAM, filters.testRunIds.join(','));
  }

  if (scope?.requirementId) {
    params.set('requirementId', scope.requirementId);
  }
  if (scope?.requirementName) {
    params.set('requirementName', scope.requirementName);
  }
  if (scope?.impactId) {
    params.set('impactId', scope.impactId);
  }
  if (scope?.impactName) {
    params.set('impactName', scope.impactName);
  }
  if (scope?.requirementParentId) {
    params.set('requirementParentId', scope.requirementParentId);
  }
  if (scope?.requirementParentName) {
    params.set('requirementParentName', scope.requirementParentName);
  }
  if (scope?.metricName) {
    params.set('metric', scope.metricName);
  }
  if (scope?.topicId) {
    params.set('topicId', scope.topicId);
  }
  if (scope?.topicName) {
    params.set('topic', scope.topicName);
  }
  if (scope?.outcome === INSIGHTS_OUTCOME_ALL) {
    params.set('outcome', INSIGHTS_OUTCOME_ALL);
  }

  return `/tests?${params.toString()}`;
}

type LegacyTestRunScope = 'default' | 'all' | 'custom';

function parseLegacyFilters(
  searchParams: Pick<URLSearchParams, 'get'>
): Pick<
  InsightsFailedTestsFilter,
  'runFilterMode' | 'timeRange' | 'testRunIds'
> | null {
  const runFilterMode = searchParams.get(
    INSIGHTS_RUN_FILTER_MODE_PARAM
  ) as InsightsRunFilterMode | null;
  if (runFilterMode === 'timeRange' || runFilterMode === 'testRuns') {
    const timeRange = searchParams.get(INSIGHTS_TIME_RANGE_PARAM);
    const rawTestRunIds = searchParams.get(INSIGHTS_TEST_RUN_IDS_PARAM);
    return {
      runFilterMode,
      timeRange: resolveInsightsTimeRange(
        (timeRange as InsightsTimeRange | null) ?? undefined
      ),
      testRunIds:
        runFilterMode === 'testRuns' && rawTestRunIds
          ? rawTestRunIds.split(',').filter(Boolean)
          : [],
    };
  }

  const legacyScope = searchParams.get(
    INSIGHTS_TEST_RUN_SCOPE_PARAM
  ) as LegacyTestRunScope | null;
  const legacyTimeRange = searchParams.get(INSIGHTS_TIME_RANGE_PARAM);

  if (legacyScope === 'custom') {
    const rawTestRunIds = searchParams.get(INSIGHTS_TEST_RUN_IDS_PARAM);
    return {
      runFilterMode: 'testRuns',
      timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
      testRunIds: rawTestRunIds ? rawTestRunIds.split(',').filter(Boolean) : [],
    };
  }

  if (legacyScope === 'all') {
    return {
      runFilterMode: 'testRuns',
      timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
      testRunIds: [],
    };
  }

  if (legacyScope === 'default' || legacyTimeRange) {
    return {
      runFilterMode: 'timeRange',
      timeRange: resolveInsightsTimeRange(
        (legacyTimeRange as InsightsTimeRange | null) ?? undefined
      ),
      testRunIds: [],
    };
  }

  return null;
}

const DEFAULT_INSIGHTS_TIME_RANGE = resolveInsightsTimeRange(undefined);

export function parseInsightsFailedTestsSearchParams(
  searchParams: Pick<URLSearchParams, 'get'>
): InsightsFailedTestsFilter | null {
  if (searchParams.get(INSIGHTS_FAILED_TESTS_QUERY) !== '1') {
    return null;
  }

  const endpointId = searchParams.get('endpointId');
  if (!endpointId) {
    return null;
  }

  const runFilters = parseLegacyFilters(searchParams);
  if (!runFilters) {
    return null;
  }

  return {
    endpointId,
    ...runFilters,
    requirementId: searchParams.get('requirementId') || undefined,
    requirementName: searchParams.get('requirementName') || undefined,
    impactId: searchParams.get('impactId') || undefined,
    impactName: searchParams.get('impactName') || undefined,
    requirementParentId: searchParams.get('requirementParentId') || undefined,
    requirementParentName:
      searchParams.get('requirementParentName') || undefined,
    metricName: searchParams.get('metric') || undefined,
    topicId: searchParams.get('topicId') || undefined,
    topicName: searchParams.get('topic') || undefined,
    outcome:
      searchParams.get('outcome') === INSIGHTS_OUTCOME_ALL ? 'all' : 'failed',
  };
}

/**
 * Resolve test case IDs that failed for the selected Insights scope,
 * optionally scoped to a requirement, metric, or topic row.
 *
 * Delegates to GET /insights/ids, which resolves matching test_ids
 * server-side (a Postgres query over the stats view) instead of
 * paginating full TestResultDetail rows and filtering them here.
 */
export async function fetchFailedTestIdsForInsights(
  filters: InsightsRunContextFilters & InsightsFailedTestsScope
): Promise<string[]> {
  if (!filters.endpointId) {
    return [];
  }

  // Empty `testRunIds` is meaningful: time-range mode and testRuns/"all runs"
  // both store `[]` and need resolution via `resolveInsightsQueryTestRunIds`.
  // Do not treat `[]` as missing (`??` would skip resolution).
  const testRunIds =
    filters.testRunIds.length > 0
      ? filters.testRunIds
      : await resolveInsightsQueryTestRunIds(filters);
  if (testRunIds.length === 0) {
    return [];
  }

  const client = new ApiClientFactory().getInsightsClient();
  const result = await client.getInsightsIds({
    entity: filters.metricName ? 'metric' : 'test_result',
    test_run_ids: testRunIds,
    outcome: filters.outcome === 'all' ? 'all' : 'fail',
    ...(filters.requirementId
      ? { requirement_ids: [filters.requirementId] }
      : {}),
    ...(filters.impactId ? { impact_ids: [filters.impactId] } : {}),
    ...(filters.requirementParentId
      ? { requirement_parent_ids: [filters.requirementParentId] }
      : {}),
    ...(filters.metricName ? { metric_names: [filters.metricName] } : {}),
    ...(filters.topicId ? { topic_ids: [filters.topicId] } : {}),
  });

  return result.ids ?? [];
}

export function formatInsightsSummaryDetail(
  passed: number,
  total: number,
  failed: number
): string {
  let detail = `(${passed}/${total} test results passed`;
  if (failed > 0) {
    detail += `, ${failed}/${total} failed`;
  }
  detail += ')';
  return detail;
}

export function formatInsightsTimeRangeLabel(
  timeRange: InsightsTimeRange
): string {
  switch (timeRange) {
    case 'always':
      return 'all time';
    case '1d':
      return '1 day';
    case '7d':
      return '7 days';
    case '1m':
      return '1 month';
    case '3m':
      return '3 months';
  }
}

export function formatInsightsRunFilterLabel(
  filter: Pick<
    InsightsFailedTestsFilter,
    'runFilterMode' | 'timeRange' | 'testRunIds'
  >
): string {
  if (filter.runFilterMode === 'timeRange') {
    const timeRange = resolveInsightsTimeRange(filter.timeRange);
    if (timeRange === 'always') {
      return 'all time';
    }
    return `the last ${formatInsightsTimeRangeLabel(timeRange)}`;
  }
  if (filter.testRunIds.length === 0) {
    return 'all test runs';
  }
  const count = filter.testRunIds.length;
  return `${count} selected test run${count === 1 ? '' : 's'}`;
}

export function formatInsightsFailedTestsBanner(
  filter: InsightsFailedTestsFilter,
  count: number,
  endpointName?: string
): string {
  const endpoint = endpointName ?? 'the selected endpoint';
  const period = formatInsightsRunFilterLabel(filter);
  const noun = `test case${count === 1 ? '' : 's'}`;

  const showAll = filter.outcome === 'all';
  const group = insightsScopeGroupName(filter);

  if (count === 0) {
    return showAll
      ? 'No test cases matched your Insights filters.'
      : 'No failed test cases matched your Insights filters.';
  }

  if (filter.metricName && group) {
    if (showAll) {
      return `Showing ${count} ${noun} evaluated for "${filter.metricName}" in ${group} on ${endpoint} for ${period}.`;
    }
    return `Showing ${count} ${noun} where "${filter.metricName}" failed for ${group} on ${endpoint} for ${period}.`;
  }

  if (filter.topicName && group) {
    if (showAll) {
      return `Showing ${count} ${noun} for topic "${filter.topicName}" in ${group} on ${endpoint} for ${period}.`;
    }
    return `Showing ${count} failed ${noun} for topic "${filter.topicName}" in ${group} on ${endpoint} for ${period}.`;
  }

  if (group) {
    return showAll
      ? `Showing ${count} ${noun} for ${group} on ${endpoint} for ${period}.`
      : `Showing ${count} failed ${noun} for ${group} on ${endpoint} for ${period}.`;
  }

  return showAll
    ? `Showing ${count} ${noun} for ${endpoint} for ${period}.`
    : `Showing ${count} failed ${noun} for ${endpoint} for ${period}.`;
}

export function insightsFailedFilterToRunContext(
  filter: InsightsFailedTestsFilter
): InsightsRunContextFilters {
  return {
    endpointId: filter.endpointId,
    runFilterMode: filter.runFilterMode,
    timeRange: filter.timeRange,
    testRunIds: filter.testRunIds,
  };
}
