import { renderHook, waitFor } from '@testing-library/react';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';
import { useBehaviorInsightsData } from '../useBehaviorInsightsData';

jest.mock('../../utils/behavior-insights-utils', () => ({
  resolveInsightsQueryTestRunIds: jest.fn(),
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

import { resolveInsightsQueryTestRunIds } from '../../utils/behavior-insights-utils';
import { fetchFailedTestIdsForInsights } from '../../utils/insights-failed-tests';

const mockResolveTestRunIds = resolveInsightsQueryTestRunIds as jest.Mock;
const mockFetchFailedIds = fetchFailedTestIdsForInsights as jest.Mock;

describe('useBehaviorInsightsData', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockResolveTestRunIds.mockReset();
    mockFetchFailedIds.mockReset();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('resolves deduped failedTestCaseCount when summary has failures', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1', 'run-2']);
    mockFetchFailedIds.mockResolvedValue([
      'test-1',
      'test-2',
      'test-3',
      'test-4',
      'test-5',
    ]);

    const filters = {
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-1',
    };

    const { result } = renderHook(() =>
      useBehaviorInsightsData('token', filters)
    );

    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    await waitFor(() => {
      expect(result.current.failedTestCaseCount).toBe(5);
    });

    expect(result.current.summary?.failed).toBe(10);
    expect(mockFetchFailedIds).toHaveBeenCalledWith('token', {
      endpointId: 'ep-1',
      runFilterMode: 'timeRange',
      timeRange: '1m',
      testRunIds: ['run-1', 'run-2'],
    });
  });

  it('finishes main loading before unique failed count resolves', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1']);
    let resolveFailed!: (ids: string[]) => void;
    mockFetchFailedIds.mockImplementation(
      () =>
        new Promise<string[]>(resolve => {
          resolveFailed = resolve;
        })
    );

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
    expect(result.current.failedTestCaseCount).toBeNull();

    resolveFailed(['test-1']);
    await waitFor(() => {
      expect(result.current.failedTestCaseCount).toBe(1);
    });
  });

  it('still renders insights when unique failed count fetch fails', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1']);
    mockFetchFailedIds.mockRejectedValue(new Error('network'));

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

    expect(result.current.error).toBeNull();
    expect(result.current.summary?.failed).toBe(10);
    await waitFor(() => {
      expect(result.current.failedTestCaseCount).toBe(0);
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

    mockResolveTestRunIds.mockResolvedValue(['run-1']);

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

  it('does not fetch when enabled is false, even with a valid endpointId', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1']);

    const { result } = renderHook(() =>
      useBehaviorInsightsData(
        'token',
        {
          ...DEFAULT_INSIGHTS_FILTERS,
          endpointId: 'ep-1',
        },
        false
      )
    );

    jest.advanceTimersByTime(300);

    expect(result.current.loading).toBe(false);
    expect(result.current.summary).toBeNull();
    expect(mockResolveTestRunIds).not.toHaveBeenCalled();
  });

  it('starts fetching once enabled flips from false to true', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1']);

    const filters = {
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-1',
    };

    const { result, rerender } = renderHook(
      ({ enabled }) => useBehaviorInsightsData('token', filters, enabled),
      { initialProps: { enabled: false } }
    );

    jest.advanceTimersByTime(300);
    expect(mockResolveTestRunIds).not.toHaveBeenCalled();

    rerender({ enabled: true });
    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(mockResolveTestRunIds).toHaveBeenCalledWith('token', filters);
  });
});
