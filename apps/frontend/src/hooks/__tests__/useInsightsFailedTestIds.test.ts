import { QueryClient } from '@tanstack/react-query';
import {
  fetchInsightsFailedTestIds,
  toInsightsFailedTestIdsScope,
} from '../useInsightsFailedTestIds';

jest.mock('@/app/(protected)/insights/utils/behavior-insights-utils', () => ({
  resolveInsightsQueryTestRunIds: jest.fn(),
}));

jest.mock('@/app/(protected)/insights/utils/insights-failed-tests', () => ({
  fetchFailedTestIdsForInsights: jest.fn(),
}));

import { resolveInsightsQueryTestRunIds } from '@/app/(protected)/insights/utils/behavior-insights-utils';
import { fetchFailedTestIdsForInsights } from '@/app/(protected)/insights/utils/insights-failed-tests';

const mockResolve = resolveInsightsQueryTestRunIds as jest.Mock;
const mockFetchIds = fetchFailedTestIdsForInsights as jest.Mock;

describe('toInsightsFailedTestIdsScope', () => {
  it('normalizes omitted outcome and failed to the same key', () => {
    const base = {
      endpointId: 'ep-1',
      runFilterMode: 'timeRange' as const,
      timeRange: '1m' as const,
      testRunIds: [] as string[],
    };
    expect(toInsightsFailedTestIdsScope(base).outcome).toBe('failed');
    expect(
      toInsightsFailedTestIdsScope({ ...base, outcome: 'failed' }).outcome
    ).toBe('failed');
    expect(
      toInsightsFailedTestIdsScope({ ...base, outcome: 'all' }).outcome
    ).toBe('all');
  });

  it('sorts testRunIds for stable keys', () => {
    const scope = toInsightsFailedTestIdsScope({
      endpointId: 'ep-1',
      runFilterMode: 'testRuns',
      timeRange: '1m',
      testRunIds: ['b', 'a'],
    });
    expect(scope.testRunIds).toEqual(['a', 'b']);
  });
});

describe('fetchInsightsFailedTestIds', () => {
  beforeEach(() => {
    mockResolve.mockReset();
    mockFetchIds.mockReset();
  });

  it('reuses the React Query cache across callers with the same scope', async () => {
    mockResolve.mockResolvedValue(['run-1']);
    mockFetchIds.mockResolvedValue(['t1', 't2']);

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: 5 * 60_000 },
      },
    });
    const filters = {
      endpointId: 'ep-1',
      runFilterMode: 'timeRange' as const,
      timeRange: '1m' as const,
      testRunIds: [] as string[],
      outcome: 'failed' as const,
    };

    const first = await fetchInsightsFailedTestIds(queryClient, filters);
    const second = await fetchInsightsFailedTestIds(queryClient, filters);

    expect(first).toEqual(['t1', 't2']);
    expect(second).toEqual(['t1', 't2']);
    expect(mockResolve).toHaveBeenCalledTimes(1);
    expect(mockFetchIds).toHaveBeenCalledTimes(1);
  });
});
