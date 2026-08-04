import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';
import { useBehaviorInsightsData } from '../useBehaviorInsightsData';

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok' },
    status: 'authenticated',
  }),
}));

jest.mock('../../utils/behavior-insights-utils', () => ({
  resolveInsightsQueryTestRunIds: jest.fn(),
  buildBehaviorColumns: jest.fn(() => []),
  rowToPassFailStats: jest.fn(row => ({
    total: Number(row.count ?? 0),
    passed: Number(row.passed ?? 0),
    failed: Number(row.failed ?? 0),
    pass_rate: Number(row.pass_rate ?? 0),
  })),
}));

function mockInsightsBatchResponse(summaryRow: {
  count: number;
  passed: number;
  failed: number;
  pass_rate: number;
}) {
  return {
    results: {
      summary: {
        entity: 'test_result',
        dimensions: [],
        measures: ['count', 'passed', 'failed', 'pass_rate'],
        rows: [summaryRow],
      },
      behaviors: {
        entity: 'test_result',
        dimensions: ['behavior_id', 'behavior'],
        measures: ['count', 'passed', 'failed', 'pass_rate'],
        rows: [],
      },
      topics: {
        entity: 'test_result',
        dimensions: ['behavior_id', 'topic'],
        measures: ['count', 'passed', 'failed', 'pass_rate'],
        rows: [],
      },
      metrics: {
        entity: 'metric',
        dimensions: ['behavior_id', 'metric_name'],
        measures: ['count', 'passed', 'failed', 'pass_rate'],
        rows: [],
      },
    },
  };
}

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getInsightsClient: () => ({
      getInsightsBatch: jest.fn().mockResolvedValue(
        mockInsightsBatchResponse({
          count: 20,
          passed: 10,
          failed: 10,
          pass_rate: 50,
        })
      ),
    }),
  })),
}));

import { resolveInsightsQueryTestRunIds } from '../../utils/behavior-insights-utils';

const mockResolveTestRunIds = resolveInsightsQueryTestRunIds as jest.Mock;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

describe('useBehaviorInsightsData', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockResolveTestRunIds.mockReset();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('resolves summary from the batch response', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1', 'run-2']);

    const filters = {
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-1',
    };

    const { result } = renderHook(() => useBehaviorInsightsData(filters), {
      wrapper: createWrapper(),
    });

    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.summary?.failed).toBe(10);
    expect(result.current.summary?.passed).toBe(10);
  });

  it('does not fetch when enabled is false, even with a valid endpointId', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1']);

    const { result } = renderHook(
      () =>
        useBehaviorInsightsData(
          {
            ...DEFAULT_INSIGHTS_FILTERS,
            endpointId: 'ep-1',
          },
          false
        ),
      { wrapper: createWrapper() }
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
      ({ enabled }) => useBehaviorInsightsData(filters, enabled),
      { initialProps: { enabled: false }, wrapper: createWrapper() }
    );

    jest.advanceTimersByTime(300);
    expect(mockResolveTestRunIds).not.toHaveBeenCalled();

    rerender({ enabled: true });
    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(mockResolveTestRunIds).toHaveBeenCalledWith({
      endpointId: 'ep-1',
      runFilterMode: 'timeRange',
      timeRange: '1m',
      testRunIds: [],
    });
  });
});
