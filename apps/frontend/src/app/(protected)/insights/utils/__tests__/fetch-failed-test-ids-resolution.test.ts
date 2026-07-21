/**
 * Isolation tests for resolve behavior when `testRunIds` is empty.
 * Kept separate so we can mock `resolveInsightsQueryTestRunIds` without
 * affecting URL/format unit tests.
 */
jest.mock('../behavior-insights-utils', () => ({
  resolveInsightsQueryTestRunIds: jest.fn(),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestResultsClient: () => ({
      getTestResults: jest.fn().mockResolvedValue({
        data: [{ test_id: 'test-1' }],
        pagination: { totalCount: 1 },
      }),
    }),
  })),
}));

import { resolveInsightsQueryTestRunIds } from '../behavior-insights-utils';
import { fetchFailedTestIdsForInsights } from '../insights-failed-tests';

const mockResolve = resolveInsightsQueryTestRunIds as jest.Mock;

describe('fetchFailedTestIdsForInsights resolution', () => {
  beforeEach(() => {
    mockResolve.mockReset();
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
    expect(ids).toEqual(['test-1']);
  });
});
