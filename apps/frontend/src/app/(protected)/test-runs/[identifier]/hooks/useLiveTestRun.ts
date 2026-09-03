'use client';

import { useQuery } from '@tanstack/react-query';
import { testRunKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { isTerminalRunStatus } from '@/constants/test-runs';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

const POLL_MS = 3000;

/**
 * Keeps testRun fresh while a run is in progress. The initial render is
 * server-fetched (page.tsx) as a one-shot snapshot that never updates on
 * its own -- unlike the verdict grid (useTestRunLive), which already polls
 * and subscribes live. Without this, status-derived UI (the header's status
 * pill) stays stuck on whatever the run's status was at page load, even
 * after the grid has already moved on to a terminal state.
 */
export function useLiveTestRun(
  testRunId: string,
  initialTestRun: TestRunDetail
): TestRunDetail {
  const { data } = useQuery<TestRunDetail>({
    queryKey: testRunKeys.detail(testRunId),
    queryFn: () =>
      new ApiClientFactory().getTestRunsClient().getTestRun(testRunId),
    initialData: initialTestRun,
    // The server just fetched this -- trust it at mount instead of
    // immediately re-requesting the same data; refetchInterval is what
    // keeps it fresh from here.
    refetchOnMount: false,
    refetchInterval: query => {
      const status = query.state.data?.status?.name?.toLowerCase() ?? '';
      return isTerminalRunStatus(status) ? false : POLL_MS;
    },
  });
  return data;
}
