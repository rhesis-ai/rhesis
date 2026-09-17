'use client';

import { useQuery } from '@tanstack/react-query';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { readActiveProjectId } from '@/utils/active-project';
import { testRunUsageKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

const POLL_MS = 3000;

/** Key scope for a render that has no active project yet; never fetched. */
const NO_PROJECT = 'no-project';

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
 * Asked of how many traces enrichment has been through, not of the cost itself.
 * Cost cannot answer it: `total_cost_usd` is 0 for a run nobody has priced yet,
 * for one whose models LiteLLM cannot price, and for one that genuinely cost
 * nothing, and waiting on that zero would either stop too early or never stop.
 */
function isSettled(usage: TraceMetricsResponse): boolean {
  return usage.enriched_traces >= usage.total_traces;
}

/**
 * Whether the cost on screen is a figure somebody computed.
 *
 * A run with priced traces that add up to zero really did cost nothing and
 * should say so. A run with none has a zero that means "no idea", and shows a
 * dash instead.
 */
export function isCostKnown(usage: TraceMetricsResponse): boolean {
  return usage.priced_traces > 0;
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
  // A backstop, not the stop condition: enrichment that dies mid-run leaves
  // traces unprocessed forever, and the card should not wait forever with it.
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
 * about to arrive. It stops once enrichment has been through every trace in the
 * run, with a two-minute backstop from the run's end for the case where
 * enrichment dies partway and those traces never get processed at all.
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
    // A sentinel rather than an empty string, so a render with no project yet
    // cannot share a cache entry with a real one or be swept up by a prefix
    // invalidation aimed at it.
    queryKey: testRunUsageKeys.detail(projectId ?? NO_PROJECT, testRun.id),
    queryFn: () => {
      // Unreachable while `enabled` holds; narrowing it here is what lets the
      // request and the cache key name the same project instead of each
      // falling back on its own.
      if (!projectId) throw new Error('No active project');
      return new ApiClientFactory(undefined, projectId)
        .getTelemetryClient()
        .getMetrics({ project_id: projectId, test_run_id: testRun.id });
    },
    enabled: Boolean(projectId && testRun.id),
    refetchInterval: query =>
      nextPollDelay(query.state.data, isRunning, finishedAt),
  });

  // The card is supplementary, so a failed request renders nothing rather than
  // taking the summary down. useQuery already swallows the throw.
  return data ?? null;
}
