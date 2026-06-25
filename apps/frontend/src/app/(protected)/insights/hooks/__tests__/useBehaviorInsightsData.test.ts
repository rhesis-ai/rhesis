import { renderHook, waitFor } from '@testing-library/react';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';
import { useBehaviorInsightsData } from '../useBehaviorInsightsData';

jest.mock('../../utils/behavior-insights-utils', () => ({
  fetchTestRunIdsForEndpoint: jest.fn(),
  buildBehaviorColumns: jest.fn(() => []),
}));

jest.mock('../../utils/insights-failed-tests', () => ({
  fetchFailedTestIdsForInsights: jest.fn(),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestResultsClient: () => ({
      getComprehensiveTestResultsStats: jest.fn().mockResolvedValue({
        overall_pass_rates: {
          total: 20,
          passed: 10,
          failed: 10,
          pass_rate: 50,
        },
        behavior_pass_rates: {},
        metadata: null,
      }),
    }),
    getBehaviorClient: () => ({
      getBehaviors: jest.fn().mockResolvedValue([]),
    }),
  })),
}));

import { fetchTestRunIdsForEndpoint } from '../../utils/behavior-insights-utils';
import { fetchFailedTestIdsForInsights } from '../../utils/insights-failed-tests';

const mockFetchTestRunIds = fetchTestRunIdsForEndpoint as jest.Mock;
const mockFetchFailedIds = fetchFailedTestIdsForInsights as jest.Mock;

describe('useBehaviorInsightsData', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockFetchTestRunIds.mockReset();
    mockFetchFailedIds.mockReset();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('resolves deduped failedTestCaseCount when summary has failures', async () => {
    mockFetchTestRunIds.mockResolvedValue(['run-1', 'run-2']);
    mockFetchFailedIds.mockResolvedValue([
      'test-1',
      'test-2',
      'test-3',
      'test-4',
      'test-5',
    ]);

    const { result } = renderHook(() =>
      useBehaviorInsightsData('token', {
        ...DEFAULT_INSIGHTS_FILTERS,
        endpointId: 'ep-1',
        timeRange: '1m',
      })
    );

    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.summary?.failed).toBe(10);
    expect(result.current.failedTestCaseCount).toBe(5);
    expect(mockFetchFailedIds).toHaveBeenCalledWith('token', {
      endpointId: 'ep-1',
      timeRange: '1m',
    });
  });

  it('skips failed ID fetch when summary has zero failures', async () => {
    const { ApiClientFactory } = jest.requireMock(
      '@/utils/api-client/client-factory'
    );
    ApiClientFactory.mockImplementation(() => ({
      getTestResultsClient: () => ({
        getComprehensiveTestResultsStats: jest.fn().mockResolvedValue({
          overall_pass_rates: {
            total: 10,
            passed: 10,
            failed: 0,
            pass_rate: 100,
          },
          behavior_pass_rates: {},
          metadata: null,
        }),
      }),
      getBehaviorClient: () => ({
        getBehaviors: jest.fn().mockResolvedValue([]),
      }),
    }));

    mockFetchTestRunIds.mockResolvedValue(['run-1']);

    const { result } = renderHook(() =>
      useBehaviorInsightsData('token', {
        ...DEFAULT_INSIGHTS_FILTERS,
        endpointId: 'ep-1',
      })
    );

    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.failedTestCaseCount).toBe(0);
    expect(mockFetchFailedIds).not.toHaveBeenCalled();
  });
});
