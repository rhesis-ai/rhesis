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

/** Sort ascending by pass rate (worst first). */
export function sortByPassRateAsc<T extends { pass_rate: number }>(
  items: T[]
): T[] {
  return [...items].sort((a, b) => a.pass_rate - b.pass_rate);
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

export function resolveEndpointId(
  endpoints: Endpoint[],
  projectId: string | undefined
): string | null {
  const projectEndpoints = projectId
    ? endpoints.filter(e => e.project_id === projectId)
    : endpoints;

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

export async function fetchTestRunIdsForEndpoint(
  sessionToken: string,
  endpointId: string
): Promise<string[]> {
  const client = new ApiClientFactory(sessionToken).getTestRunsClient();
  const filter = buildEndpointRunFilter(endpointId);
  const ids: string[] = [];
  let skip = 0;
  const limit = 100;
  let hasMore = true;

  while (hasMore) {
    const response = await client.getTestRuns({
      filter,
      skip,
      limit,
      sort_by: 'created_at',
      sort_order: 'desc',
    });

    ids.push(...response.data.map(run => run.id));
    const total = response.pagination?.totalCount ?? response.data.length;
    hasMore = ids.length < total;
    skip += limit;

    if (skip > 5000) break;
  }

  return ids;
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

  return sortByPassRateAsc(columns);
}
