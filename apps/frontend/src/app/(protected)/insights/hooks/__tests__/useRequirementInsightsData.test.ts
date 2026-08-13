import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DEFAULT_INSIGHTS_FILTERS } from '../../types';
import { useRequirementInsightsData } from '../useRequirementInsightsData';

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok' },
    status: 'authenticated',
  }),
}));

jest.mock('../../utils/requirement-insights-utils', () => ({
  ...jest.requireActual('../../utils/requirement-insights-utils'),
  resolveInsightsQueryTestRunIds: jest.fn(),
  buildRequirementColumns: jest.fn(() => []),
}));

function mockInsightsQueryResponse(summaryRow: {
  passed: number;
  failed: number;
  pass_rate: number;
}) {
  return {
    summary: {
      entity: 'test_result',
      dimensions: [],
      measures: ['count', 'passed', 'failed', 'pass_rate'],
      rows: [summaryRow],
    },
    requirements: {
      entity: 'test_result',
      dimensions: ['requirement_id', 'requirement'],
      measures: ['count', 'passed', 'failed', 'pass_rate'],
      rows: [],
    },
    topics: {
      entity: 'test_result',
      dimensions: ['requirement_id', 'topic_id', 'topic'],
      measures: ['count', 'passed', 'failed', 'pass_rate'],
      rows: [],
    },
    metrics: {
      entity: 'metric',
      dimensions: ['requirement_id', 'metric_name'],
      measures: ['count', 'passed', 'failed', 'pass_rate'],
      rows: [],
    },
    allRequirements: {
      entity: 'test_result',
      dimensions: ['requirement_id', 'requirement'],
      measures: ['count', 'passed', 'failed', 'pass_rate'],
      rows: [],
    },
  };
}

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getInsightsClient: () => ({
      getInsightsQuery: jest.fn().mockResolvedValue(
        mockInsightsQueryResponse({
          passed: 10,
          failed: 10,
          pass_rate: 50,
        })
      ),
    }),
  })),
}));

import { resolveInsightsQueryTestRunIds } from '../../utils/requirement-insights-utils';

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

describe('useRequirementInsightsData', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockResolveTestRunIds.mockReset();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('resolves summary from the query response', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1', 'run-2']);

    const filters = {
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-1',
    };

    const { result } = renderHook(() => useRequirementInsightsData(filters), {
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
        useRequirementInsightsData(
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
      ({ enabled }) => useRequirementInsightsData(filters, enabled),
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
      timeRange: 'always',
      testRunIds: [],
    });
  });

  it('shows zero data when requirementIds is explicitly filtered to nothing', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1']);

    const filters = {
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-1',
      requirementIds: [], // explicitly unchecked every requirement -- not "no filter"
    };

    const { result } = renderHook(() => useRequirementInsightsData(filters), {
      wrapper: createWrapper(),
    });

    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // The mocked query response reports passed:10/failed:10 -- if these
    // assertions ever pass because the hook forgot to call the API at all,
    // that's still correct; the point is the *result* must be zero either way.
    expect(result.current.summary).toEqual({
      total: 0,
      passed: 0,
      failed: 0,
      pass_rate: 0,
    });
    expect(result.current.columns).toEqual([]);
  });

  it('shows zero data when statusIds is explicitly filtered to nothing', async () => {
    mockResolveTestRunIds.mockResolvedValue(['run-1']);

    const filters = {
      ...DEFAULT_INSIGHTS_FILTERS,
      endpointId: 'ep-1',
      statusIds: [], // explicitly unchecked every status
    };

    const { result } = renderHook(() => useRequirementInsightsData(filters), {
      wrapper: createWrapper(),
    });

    jest.advanceTimersByTime(300);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.summary).toEqual({
      total: 0,
      passed: 0,
      failed: 0,
      pass_rate: 0,
    });
    expect(result.current.columns).toEqual([]);
  });
});
