import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { testRunUsageKeys } from '@/constants/query-keys';
import { nextPollDelay, useTestRunUsage } from '../useTestRunUsage';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

const getMetrics = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTelemetryClient: () => ({ getMetrics }),
  })),
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ activeProject: { id: 'project-1' } }),
}));

jest.mock('@/utils/active-project', () => ({
  readActiveProjectId: () => 'project-1',
}));

const POLL_MS = 3000;
const MINUTE = 60 * 1000;

function usage(overrides: Partial<TraceMetricsResponse> = {}) {
  return {
    total_traces: 4,
    total_spans: 12,
    total_tokens: 900,
    total_cost_usd: 0,
    error_rate: 0,
    avg_duration_ms: 1,
    p50_duration_ms: 1,
    p95_duration_ms: 1,
    p99_duration_ms: 1,
    operation_breakdown: {},
    ...overrides,
  } as TraceMetricsResponse;
}

function run(completedAt?: string): TestRunDetail {
  return {
    id: 'run-1',
    attributes: completedAt ? { completed_at: completedAt } : {},
  } as unknown as TestRunDetail;
}

describe('nextPollDelay', () => {
  const finishedAt = Date.parse('2026-09-17T10:00:00Z');
  const justFinished = finishedAt + 10 * 1000;
  const longFinished = finishedAt + 5 * MINUTE;

  it('polls while the run is still going, whatever the numbers say', () => {
    expect(nextPollDelay(undefined, true, null, justFinished)).toBe(POLL_MS);
    expect(
      nextPollDelay(
        usage({ total_cost_usd: 0.4 }),
        true,
        finishedAt,
        longFinished
      )
    ).toBe(POLL_MS);
  });

  it('keeps polling after the run finishes while cost has not landed', () => {
    // The case the whole hook exists for: enrichment prices a run *after* it
    // ends, so stopping on terminal status stops exactly when cost is due.
    expect(nextPollDelay(usage(), false, finishedAt, justFinished)).toBe(
      POLL_MS
    );
  });

  it('stops as soon as the run is priced', () => {
    expect(
      nextPollDelay(
        usage({ total_cost_usd: 0.03 }),
        false,
        finishedAt,
        justFinished
      )
    ).toBe(false);
  });

  it('stops for a run that traced nothing, which has nothing to price', () => {
    expect(
      nextPollDelay(
        usage({ total_tokens: 0, total_traces: 0 }),
        false,
        finishedAt,
        justFinished
      )
    ).toBe(false);
  });

  it('gives up on a run whose models will never be priced', () => {
    // Tokens but no cost, long after the run ended. Without the window this
    // polls for as long as the tab is open.
    expect(nextPollDelay(usage(), false, finishedAt, longFinished)).toBe(false);
  });

  it('does not poll a run that never recorded when it finished', () => {
    expect(nextPollDelay(usage(), false, null, longFinished)).toBe(false);
  });

  it('measures the window from when the run ended, not from when the card opened', () => {
    // Opening a year-old unpriced run must not start a fresh two minutes of
    // polling.
    const ancient = finishedAt - 365 * 24 * 60 * MINUTE;
    expect(nextPollDelay(usage(), false, ancient, finishedAt)).toBe(false);
  });
});

describe('useTestRunUsage', () => {
  let queryClient: QueryClient;

  function wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }

  beforeEach(() => {
    getMetrics.mockReset();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it('renders nothing until the numbers arrive', () => {
    getMetrics.mockResolvedValue(usage());
    const { result } = renderHook(() => useTestRunUsage(run()), { wrapper });

    expect(result.current).toBeNull();
  });

  it('scopes the request to the run and the active project', async () => {
    getMetrics.mockResolvedValue(usage());
    renderHook(() => useTestRunUsage(run()), { wrapper });

    await waitFor(() => expect(getMetrics).toHaveBeenCalled());
    expect(getMetrics).toHaveBeenCalledWith({
      project_id: 'project-1',
      test_run_id: 'run-1',
    });
  });

  it('picks up new totals as the run progresses', async () => {
    // Bypasses the interval's own timing, which fake timers and react-query's
    // scheduler do not agree on, and takes the same path a poll would.
    getMetrics.mockResolvedValue(usage({ total_tokens: 100 }));
    const { result } = renderHook(() => useTestRunUsage(run(), true), {
      wrapper,
    });
    await waitFor(() => expect(result.current?.total_tokens).toBe(100));

    getMetrics.mockResolvedValue(usage({ total_tokens: 4200 }));
    await act(async () => {
      await queryClient.invalidateQueries({
        queryKey: testRunUsageKeys.detail('project-1', 'run-1'),
      });
    });

    await waitFor(() => expect(result.current?.total_tokens).toBe(4200));
  });

  it('survives a failed request without taking the summary down', async () => {
    getMetrics.mockRejectedValue(new Error('telemetry is down'));
    const { result } = renderHook(() => useTestRunUsage(run()), { wrapper });

    await waitFor(() => expect(getMetrics).toHaveBeenCalled());
    expect(result.current).toBeNull();
  });
});
