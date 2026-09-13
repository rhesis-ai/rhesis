'use client';

import { useEffect, useState } from 'react';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { readActiveProjectId } from '@/utils/active-project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

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
 * Returns null until the numbers arrive, so callers render nothing rather than
 * zeros they do not yet have.
 */
export function useTestRunUsage(
  testRunId: string
): TraceMetricsResponse | null {
  const { activeProject } = useActiveProject();
  const projectId = activeProject?.id
    ? String(activeProject.id)
    : readActiveProjectId();
  const [usage, setUsage] = useState<TraceMetricsResponse | null>(null);

  useEffect(() => {
    if (!projectId || !testRunId) {
      setUsage(null);
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        const metrics = await new ApiClientFactory(undefined, projectId)
          .getTelemetryClient()
          .getMetrics({ project_id: projectId, test_run_id: testRunId });
        if (!cancelled) {
          setUsage(metrics);
        }
      } catch {
        // The card is supplementary; a failure here must not take the summary
        // down with it.
        if (!cancelled) {
          setUsage(null);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [projectId, testRunId]);

  return usage;
}
