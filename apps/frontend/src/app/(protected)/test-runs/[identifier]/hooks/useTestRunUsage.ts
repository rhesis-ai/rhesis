'use client';

import { useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { readActiveProjectId } from '@/utils/active-project';
import { testRunUsageKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

const POLL_MS = 3000;

/** Key scope for a render that has no active project yet; never fetched. */
const NO_PROJECT = 'no-project';

/**
 * How long the figures must hold still before the card believes enrichment has
 * caught up for good. One poll, so a run that was already finished when the
 * page opened costs two requests rather than one.
 */
const SETTLE_MS = POLL_MS;

/**
 * How long to keep asking when enrichment is behind and nothing is moving.
 *
 * This is the stalled case -- a worker that died mid-run leaves traces
 * unprocessed forever -- so it is a backstop, not the normal exit.
 */
const STALL_MS = 60 * 1000;

/** The figures whose movement means enrichment is still working. */
function signatureOf(usage: TraceMetricsResponse): string {
  return [
    usage.total_traces,
    usage.enriched_traces,
    usage.priced_traces,
    usage.total_tokens,
    usage.total_cost_usd,
  ].join('|');
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
 *
 * The signal is movement, not a deadline. Enrichment prices a run trace by
 * trace and keeps going well past the end of it -- a 60-trace run was still
 * being priced 98 seconds after it finished -- so any fixed window is either
 * too short for a big run or pure waiting for a small one.
 *
 * "Enrichment has caught up" is deliberately not enough on its own. Traces
 * arrive in batches, and between two batches enrichment catches up with
 * everything ingested so far, which looks exactly like being finished. So a
 * caught-up reading has to survive one more poll unchanged before the card
 * believes it.
 */
export function nextPollDelay(
  usage: TraceMetricsResponse | undefined,
  isRunning: boolean,
  msSinceChange: number
): number | false {
  if (isRunning || !usage) return POLL_MS;
  const caughtUp = usage.enriched_traces >= usage.total_traces;
  return msSinceChange < (caughtUp ? SETTLE_MS : STALL_MS) ? POLL_MS : false;
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
 * Polling does not stop when the run does: enrichment prices a run *after* it
 * finishes, so stopping on terminal status would stop exactly when the cost is
 * about to arrive. See `nextPollDelay` for when it does stop.
 *
 * Returns null until the numbers arrive, so callers render nothing rather than
 * zeros they do not yet have.
 */
export function useTestRunUsage(
  testRunId: string,
  isRunning = false
): TraceMetricsResponse | null {
  const { activeProject } = useActiveProject();
  const projectId = activeProject?.id
    ? String(activeProject.id)
    : readActiveProjectId();

  // When the figures last moved. Written from refetchInterval rather than
  // during render, so it tracks responses rather than re-renders.
  const lastChange = useRef({ signature: '', at: 0 });

  const { data } = useQuery<TraceMetricsResponse>({
    // A sentinel rather than an empty string, so a render with no project yet
    // cannot share a cache entry with a real one or be swept up by a prefix
    // invalidation aimed at it.
    queryKey: testRunUsageKeys.detail(projectId ?? NO_PROJECT, testRunId),
    queryFn: () => {
      // Unreachable while `enabled` holds; narrowing it here is what lets the
      // request and the cache key name the same project instead of each
      // falling back on its own.
      if (!projectId) throw new Error('No active project');
      return new ApiClientFactory(undefined, projectId)
        .getTelemetryClient()
        .getMetrics({ project_id: projectId, test_run_id: testRunId });
    },
    enabled: Boolean(projectId && testRunId),
    refetchInterval: query => {
      const usage = query.state.data;
      const signature = usage ? signatureOf(usage) : '';
      const now = Date.now();
      if (signature !== lastChange.current.signature) {
        lastChange.current = { signature, at: now };
      }
      return nextPollDelay(usage, isRunning, now - lastChange.current.at);
    },
  });

  // The card is supplementary, so a failed request renders nothing rather than
  // taking the summary down. useQuery already swallows the throw.
  return data ?? null;
}
