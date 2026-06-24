import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { TEST_RESULT_STATUS_NAMES } from '@/utils/test-result-status';
import {
  InsightsFilters,
  InsightsTimeRange,
  resolveInsightsTimeRange,
  timeRangeToStatsParams,
} from '../types';
import { fetchTestRunIdsForEndpoint } from './behavior-insights-utils';

export const INSIGHTS_FAILED_TESTS_QUERY = 'failedFromInsights';
export const INSIGHTS_OUTCOME_ALL = 'all';

export type InsightsTestOutcome = 'failed' | 'all';

export interface InsightsFailedTestsScope {
  behaviorId?: string;
  behaviorName?: string;
  metricName?: string;
  topicName?: string;
  outcome?: InsightsTestOutcome;
}

export interface InsightsFailedTestsFilter {
  endpointId: string;
  timeRange: InsightsTimeRange;
  behaviorId?: string;
  behaviorName?: string;
  metricName?: string;
  topicName?: string;
  outcome?: InsightsTestOutcome;
}

function escapeODataValue(value: string): string {
  return value.replace(/'/g, "''");
}

export function buildInsightsFailedTestsUrl(
  filters: InsightsFilters,
  scope?: InsightsFailedTestsScope
): string {
  const params = new URLSearchParams({
    [INSIGHTS_FAILED_TESTS_QUERY]: '1',
    endpointId: filters.endpointId,
    timeRange: filters.timeRange,
  });

  if (scope?.behaviorId) {
    params.set('behaviorId', scope.behaviorId);
  }
  if (scope?.behaviorName) {
    params.set('behaviorName', scope.behaviorName);
  }
  if (scope?.metricName) {
    params.set('metric', scope.metricName);
  }
  if (scope?.topicName) {
    params.set('topic', scope.topicName);
  }
  if (scope?.outcome === INSIGHTS_OUTCOME_ALL) {
    params.set('outcome', INSIGHTS_OUTCOME_ALL);
  }

  return `/tests?${params.toString()}`;
}

export function parseInsightsFailedTestsSearchParams(
  searchParams: Pick<URLSearchParams, 'get'>
): InsightsFailedTestsFilter | null {
  if (searchParams.get(INSIGHTS_FAILED_TESTS_QUERY) !== '1') {
    return null;
  }

  const endpointId = searchParams.get('endpointId');
  const timeRange = searchParams.get('timeRange');
  if (!endpointId || !timeRange) {
    return null;
  }

  return {
    endpointId,
    timeRange: resolveInsightsTimeRange(timeRange as InsightsTimeRange),
    behaviorId: searchParams.get('behaviorId') || undefined,
    behaviorName: searchParams.get('behaviorName') || undefined,
    metricName: searchParams.get('metric') || undefined,
    topicName: searchParams.get('topic') || undefined,
    outcome:
      searchParams.get('outcome') === INSIGHTS_OUTCOME_ALL ? 'all' : 'failed',
  };
}

function buildCreatedAtFilter(timeRange: InsightsTimeRange): string {
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

function normalizeId(value: unknown): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  return String(value);
}

function matchesMetricScope(
  result: TestResultDetail,
  behaviorId: string,
  metricName: string,
  failedOnly: boolean
): boolean {
  if (normalizeId(result.test?.behavior?.id) !== behaviorId) {
    return false;
  }
  const metric = result.test_metrics?.metrics?.[metricName];
  if (metric === undefined) {
    return false;
  }
  return failedOnly ? metric.is_successful === false : true;
}

function matchesBehaviorScope(
  result: TestResultDetail,
  behaviorId: string
): boolean {
  return normalizeId(result.test?.behavior?.id) === behaviorId;
}

async function filterTestIdsByTopic(
  sessionToken: string,
  testIds: string[],
  topicName: string
): Promise<string[]> {
  if (testIds.length === 0) {
    return [];
  }

  const client = new ApiClientFactory(sessionToken).getTestsClient();
  const escapedTopic = escapeODataValue(topicName);
  const matched = new Set<string>();
  const chunkSize = 40;

  for (let i = 0; i < testIds.length; i += chunkSize) {
    const chunk = testIds.slice(i, i + chunkSize);
    const idExpr = chunk
      .map(id => `id eq '${escapeODataValue(id)}'`)
      .join(' or ');
    const filter = `(${idExpr}) and tolower(topic/name) eq tolower('${escapedTopic}')`;
    const response = await client.getTests({
      filter,
      skip: 0,
      limit: chunkSize,
    });
    response.data.forEach(test => matched.add(String(test.id)));
  }

  return [...matched];
}

const TEST_RUN_ID_CHUNK = 15;

/**
 * Resolve test case IDs that failed for the endpoint + time window shown on Insights,
 * optionally scoped to a behavior, metric, or topic row.
 */
export async function fetchFailedTestIdsForInsights(
  sessionToken: string,
  filters: InsightsFilters & InsightsFailedTestsScope
): Promise<string[]> {
  if (!filters.endpointId) {
    return [];
  }

  const testRunIds = await fetchTestRunIdsForEndpoint(
    sessionToken,
    filters.endpointId
  );
  if (testRunIds.length === 0) {
    return [];
  }

  const client = new ApiClientFactory(sessionToken).getTestResultsClient();
  const ids = new Set<string>();
  const createdAtFilter = buildCreatedAtFilter(filters.timeRange);
  const failedOnly = filters.outcome !== 'all';
  const statusFilter = `status/name eq '${TEST_RESULT_STATUS_NAMES.FAILED}'`;

  for (let i = 0; i < testRunIds.length; i += TEST_RUN_ID_CHUNK) {
    const chunk = testRunIds.slice(i, i + TEST_RUN_ID_CHUNK);
    const runExpr = chunk.map(id => `test_run_id eq '${id}'`).join(' or ');
    const parts = [`(${runExpr})`];
    if (failedOnly) {
      parts.push(statusFilter);
    }
    if (filters.behaviorId) {
      parts.push(
        `test/behavior_id eq '${escapeODataValue(filters.behaviorId)}'`
      );
    }
    if (createdAtFilter) {
      parts.push(createdAtFilter);
    }
    const filter = parts.join(' and ');

    let skip = 0;
    const limit = 100;

    while (skip < 10_000) {
      const response = await client.getTestResults({ filter, skip, limit });
      response.data.forEach(result => {
        if (!result.test_id) {
          return;
        }

        if (filters.metricName && filters.behaviorId) {
          if (
            !matchesMetricScope(
              result,
              filters.behaviorId,
              filters.metricName,
              failedOnly
            )
          ) {
            return;
          }
        } else if (filters.behaviorId) {
          if (!matchesBehaviorScope(result, filters.behaviorId)) {
            return;
          }
        }

        ids.add(String(result.test_id));
      });

      const total = response.pagination?.totalCount ?? 0;
      skip += limit;
      if (skip >= total || response.data.length === 0) {
        break;
      }
    }
  }

  let testIds = [...ids];

  if (filters.topicName) {
    testIds = await filterTestIdsByTopic(
      sessionToken,
      testIds,
      filters.topicName
    );
  }

  return testIds;
}

export function formatInsightsTimeRangeLabel(
  timeRange: InsightsTimeRange
): string {
  switch (timeRange) {
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

export function formatInsightsFailedTestsBanner(
  filter: InsightsFailedTestsFilter,
  count: number,
  endpointName?: string
): string {
  const endpoint = endpointName ?? 'the selected endpoint';
  const period = formatInsightsTimeRangeLabel(filter.timeRange);
  const noun = `test case${count === 1 ? '' : 's'}`;

  const showAll = filter.outcome === 'all';

  if (count === 0) {
    return showAll
      ? 'No test cases matched your Insights filters.'
      : 'No failed test cases matched your Insights filters.';
  }

  if (filter.metricName && filter.behaviorName) {
    if (showAll) {
      return `Showing ${count} ${noun} evaluated for "${filter.metricName}" in ${filter.behaviorName} on ${endpoint} in the last ${period}.`;
    }
    return `Showing ${count} ${noun} where "${filter.metricName}" failed for ${filter.behaviorName} on ${endpoint} in the last ${period}.`;
  }

  if (filter.topicName && filter.behaviorName) {
    if (showAll) {
      return `Showing ${count} ${noun} for topic "${filter.topicName}" in ${filter.behaviorName} on ${endpoint} in the last ${period}.`;
    }
    return `Showing ${count} failed ${noun} for topic "${filter.topicName}" in ${filter.behaviorName} on ${endpoint} in the last ${period}.`;
  }

  if (filter.behaviorName) {
    return showAll
      ? `Showing ${count} ${noun} for ${filter.behaviorName} on ${endpoint} in the last ${period}.`
      : `Showing ${count} failed ${noun} for ${filter.behaviorName} on ${endpoint} in the last ${period}.`;
  }

  return `Showing ${count} failed ${noun} for ${endpoint} in the last ${period}.`;
}
