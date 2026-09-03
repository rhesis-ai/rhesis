import type { UUID } from 'crypto';
import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { Project } from '@/utils/api-client/interfaces/project';

/** Environment bindings plus the experiments they can point at (Configuration tab). */
export async function fetchProjectEnvironments(
  factory: ApiClientFactory,
  projectId: string
) {
  const client = factory.getParametersClient();
  const [bindings, experiments] = await Promise.all([
    client.getEnvironments(projectId),
    client.listProjectExperiments(projectId, { limit: 200 }),
  ]);
  return { bindings, experiments };
}

export type ProjectEnvironmentsData = Awaited<
  ReturnType<typeof fetchProjectEnvironments>
>;

/** The metric ids a project evaluates traces with, as stored on its attributes. */
export function projectTraceMetricIds(project: Project): string[] {
  const raw = project.attributes?.trace_metrics;
  return Array.isArray(raw) ? raw.map(String) : [];
}

/** The trace metrics behind `projectTraceMetricIds`, resolved to full records. */
export async function fetchProjectTraceMetrics(
  factory: ApiClientFactory,
  metricIds: string[]
): Promise<MetricDetail[]> {
  if (metricIds.length === 0) return [];
  const metricsClient = factory.getMetricsClient();
  const results = await Promise.allSettled(
    metricIds.map(id => metricsClient.getMetric(id as UUID))
  );
  return results
    .filter(
      (r): r is PromiseFulfilledResult<MetricDetail> => r.status === 'fulfilled'
    )
    .map(r => r.value)
    .filter(m => m.metric_scope?.includes('Trace'));
}
