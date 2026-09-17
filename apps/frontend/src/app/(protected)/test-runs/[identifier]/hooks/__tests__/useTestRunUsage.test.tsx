import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { testRunUsageKeys } from '@/constants/query-keys';
import {
  isCostKnown,
  nextPollDelay,
  useTestRunUsage,
} from '../useTestRunUsage';
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

/** Enrichment has not reached any of the run's traces yet. */
function usage(overrides: Partial<TraceMetricsResponse> = {}) {
  return {
    total_traces: 4,
    enriched_traces: 0,
    priced_traces: 0,
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

/** Enrichment is partway through: 40 of the run's 60 traces done. */
function behind(overrides: Partial<TraceMetricsResponse> = {}) {
  return usage({
    total_traces: 60,
    enriched_traces: 40,
    priced_traces: 40,
    total_cost_usd: 0.02,
    ...overrides,
  });
}

/** Enrichment has been through every trace and priced them. */
function priced(overrides: Partial<TraceMetricsResponse> = {}) {
  return usage({
    enriched_traces: 4,
    priced_traces: 4,
    total_cost_usd: 0.03,
    ...overrides,
  });
}

describe('nextPollDelay', () => {
  const SETTLE_MS = POLL_MS;
  const STALL_MS = 60 * 1000;

  it('polls while the run is still going, whatever the numbers say', () => {
    expect(nextPollDelay(undefined, true, 0)).toBe(POLL_MS);
    expect(nextPollDelay(priced(), true, 10 * MINUTE)).toBe(POLL_MS);
  });

  it('polls until the first response arrives', () => {
    expect(nextPollDelay(undefined, false, 10 * MINUTE)).toBe(POLL_MS);
  });

  it('keeps polling while enrichment is behind and making progress', () => {
    // The 98-second tail a real 60-trace run showed: enrichment keeps pricing
    // long after the run itself ended.
    expect(nextPollDelay(behind(), false, 2000)).toBe(POLL_MS);
    expect(nextPollDelay(behind(), false, 45 * 1000)).toBe(POLL_MS);
  });

  it('does not stop the moment enrichment happens to catch up', () => {
    // Traces arrive in batches. Between two batches everything ingested so far
    // is enriched, which reads exactly like being finished -- and a poll
    // landing in that gap used to stop the card for good.
    expect(nextPollDelay(priced(), false, 0)).toBe(POLL_MS);
    expect(nextPollDelay(priced(), false, SETTLE_MS - 1)).toBe(POLL_MS);
  });

  it('stops once a caught-up reading survives a poll unchanged', () => {
    expect(nextPollDelay(priced(), false, SETTLE_MS)).toBe(false);
  });

  it('stops for an enriched run that nothing could price', () => {
    // Enrichment finished and found no price, so waiting longer changes
    // nothing. A cost-based stop condition could never tell this from a run
    // still being priced.
    expect(
      nextPollDelay(
        usage({ enriched_traces: 4, priced_traces: 0 }),
        false,
        SETTLE_MS
      )
    ).toBe(false);
  });

  it('stops for a run that traced nothing, which has nothing to enrich', () => {
    expect(
      nextPollDelay(
        usage({ total_traces: 0, total_tokens: 0 }),
        false,
        SETTLE_MS
      )
    ).toBe(false);
  });

  it('gives up when enrichment is behind and has stalled', () => {
    // A worker that died mid-run leaves traces unprocessed forever.
    expect(nextPollDelay(behind(), false, STALL_MS)).toBe(false);
  });

  it('waits far longer on a stalled run than on a settled one', () => {
    // Being behind is the case worth being patient about; being caught up is
    // the case worth confirming quickly.
    expect(nextPollDelay(behind(), false, 10000)).toBe(POLL_MS);
    expect(nextPollDelay(priced(), false, 10000)).toBe(false);
  });
});

describe('isCostKnown', () => {
  it('trusts a zero that priced traces add up to', () => {
    // A free model costs a knowable nothing. $0.00 is the right answer here.
    expect(isCostKnown(priced({ total_cost_usd: 0 }))).toBe(true);
  });

  it('does not trust a zero nobody computed', () => {
    expect(isCostKnown(usage())).toBe(false);
    expect(isCostKnown(usage({ enriched_traces: 4, priced_traces: 0 }))).toBe(
      false
    );
  });

  it('trusts a real total', () => {
    expect(isCostKnown(priced())).toBe(true);
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
    const { result } = renderHook(() => useTestRunUsage('run-1'), { wrapper });

    expect(result.current).toBeNull();
  });

  it('scopes the request to the run and the active project', async () => {
    getMetrics.mockResolvedValue(usage());
    renderHook(() => useTestRunUsage('run-1'), { wrapper });

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
    const { result } = renderHook(() => useTestRunUsage('run-1', true), {
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
    const { result } = renderHook(() => useTestRunUsage('run-1'), { wrapper });

    await waitFor(() => expect(getMetrics).toHaveBeenCalled());
    expect(result.current).toBeNull();
  });
});
