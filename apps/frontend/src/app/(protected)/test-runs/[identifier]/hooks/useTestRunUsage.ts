'use client';

import { useQuery } from '@tanstack/react-query';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { readActiveProjectId } from '@/utils/active-project';
import { testRunUsageKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

const POLL_MS = 3000;

/** How long to keep waiting for enrichment after a run finishes. */
const PRICING_WINDOW_MS = 2 * 60 * 1000;

function completedAt(testRun: TestRunDetail): number | null {
  const value = testRun.attributes?.completed_at;
  if (typeof value !== 'string') return null;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? null : parsed;
}

/**
 * Whether the numbers have stopped moving.
 *
 * Tokens are read off the spans themselves, so they are there as soon as the
 * calls are traced. Cost is not: enrichment prices a run asynchronously, and
 * until it has, `total_cost_usd` is a real zero rather than a missing value.
 * Tokens without cost is therefore the one state that means "still working".
 * A run that traced nothing has nothing to wait for.
 */
function isSettled(usage: TraceMetricsResponse): boolean {
  return usage.total_cost_usd > 0 || usage.total_tokens === 0;
}

/**
 * How long until the card asks again, or false to stop asking.
 *
 * Every decision about when this card goes quiet is made here, which is why it
 * is exported: the alternative is testing react-query's scheduler.
 */
export function nextPollDelay(
  usage: TraceMetricsResponse | undefined,
  isRunning: boolean,
  finishedAt: number | null,
  now: number = Date.now()
): number | false {
  if (isRunning) return POLL_MS;
  if (usage && isSettled(usage)) return false;
  // No completed_at means the run never recorded one; one pass is all it gets.
  if (finishedAt === null) return false;
  return now - finishedAt < PRICING_WINDOW_MS ? POLL_MS : false;
}

/**
 * Token and cost totals for one test run's traces.
 *
 * Reads GET /telemetry/metrics rather than riding along on the verdict matrix,
 * even though the other KPI numbers live there. The matrix is cached once a run
 * goes terminal, while trace enrichment runs asynchronously after ingest, so a
 * run cached the moment it finished would report a cost of zero for the whole
 * cache lifetime. Going to the metrics endpoint also means this card and the
 * rollup tiles on the Traces tab cannot disagree.
 *
 * Polling does not stop when the run does. Enrichment prices a run *after* it
 * finishes, so stopping on terminal status would stop exactly when the cost is
 * about to arrive. It stops when the figures settle, and failing that, when the
 * run has been finished long enough that nothing more is coming -- a run whose
 * models have no published prices would otherwise poll forever.
 *
 * Returns null until the numbers arrive, so callers render nothing rather than
 * zeros they do not yet have.
 */
export function useTestRunUsage(
  testRun: TestRunDetail,
  isRunning = false
): TraceMetricsResponse | null {
  const { activeProject } = useActiveProject();
  const projectId = activeProject?.id
    ? String(activeProject.id)
    : readActiveProjectId();

  const finishedAt = completedAt(testRun);

  const { data } = useQuery<TraceMetricsResponse>({
    queryKey: testRunUsageKeys.detail(projectId ?? '', testRun.id),
    queryFn: () =>
      new ApiClientFactory(undefined, projectId ?? undefined)
        .getTelemetryClient()
        .getMetrics({
          project_id: projectId ?? '',
          test_run_id: testRun.id,
        }),
    enabled: Boolean(projectId && testRun.id),
    refetchInterval: query =>
      nextPollDelay(query.state.data, isRunning, finishedAt),
  });

  // The card is supplementary, so a failed request renders nothing rather than
  // taking the summary down. useQuery already swallows the throw.
  return data ?? null;
}
