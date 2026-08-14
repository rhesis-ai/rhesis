/**
 * Isolation tests for resolve requirement when `testRunIds` is empty.
 * Kept separate so we can mock `resolveInsightsQueryTestRunIds` without
 * affecting URL/format unit tests.
 */
jest.mock('../requirement-insights-utils', () => ({
  resolveInsightsQueryTestRunIds: jest.fn(),
}));

const mockGetInsightsIds = jest.fn().mockResolvedValue({
  entity: 'test_result',
  ids: ['test-1'],
});

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getInsightsClient: () => ({
      getInsightsIds: mockGetInsightsIds,
    }),
  })),
}));

import { resolveInsightsQueryTestRunIds } from '../requirement-insights-utils';
import { fetchFailedTestIdsForInsights } from '../insights-failed-tests';

const mockResolve = resolveInsightsQueryTestRunIds as jest.Mock;

describe('fetchFailedTestIdsForInsights resolution', () => {
  beforeEach(() => {
    mockResolve.mockReset();
    mockGetInsightsIds.mockClear();
    mockGetInsightsIds.mockResolvedValue({
      entity: 'test_result',
      ids: ['test-1'],
    });
  });

  it('resolves empty testRunIds via resolveInsightsQueryTestRunIds', async () => {
    mockResolve.mockResolvedValue(['run-a', 'run-b']);

    const ids = await fetchFailedTestIdsForInsights({
      endpointId: 'ep-1',
      runFilterMode: 'timeRange',
      timeRange: '1m',
      testRunIds: [],
    });

    expect(mockResolve).toHaveBeenCalledWith({
      endpointId: 'ep-1',
      runFilterMode: 'timeRange',
      timeRange: '1m',
      testRunIds: [],
    });
    expect(mockGetInsightsIds).toHaveBeenCalledWith({
      entity: 'test_result',
      test_run_ids: ['run-a', 'run-b'],
      outcome: 'fail',
    });
    expect(ids).toEqual(['test-1']);
  });

  it('uses provided testRunIds without calling resolve', async () => {
    const ids = await fetchFailedTestIdsForInsights({
      endpointId: 'ep-1',
      runFilterMode: 'testRuns',
      timeRange: '1m',
      testRunIds: ['run-1'],
    });

    expect(mockResolve).not.toHaveBeenCalled();
    expect(mockGetInsightsIds).toHaveBeenCalledWith({
      entity: 'test_result',
      test_run_ids: ['run-1'],
      outcome: 'fail',
    });
    expect(ids).toEqual(['test-1']);
  });

  it('uses metric entity when metricName is set', async () => {
    const ids = await fetchFailedTestIdsForInsights({
      endpointId: 'ep-1',
      runFilterMode: 'testRuns',
      timeRange: '1m',
      testRunIds: ['run-1'],
      metricName: 'Accuracy',
      requirementId: 'beh-1',
      outcome: 'all',
    });

    expect(mockGetInsightsIds).toHaveBeenCalledWith({
      entity: 'metric',
      test_run_ids: ['run-1'],
      outcome: 'all',
      requirement_ids: ['beh-1'],
      metric_names: ['Accuracy'],
    });
    expect(ids).toEqual(['test-1']);
  });
});
