import type { UUID } from 'crypto';
import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type {
  MetricTuningCase,
  MetricTuningRun,
} from '@/utils/api-client/interfaces/metric-tuning';
import type { RequirementReference } from '@/utils/api-client/interfaces/requirement';
import type { Status } from '@/utils/api-client/interfaces/status';

/** Linked requirements come back with the status relationship at runtime. */
export type LinkedRequirementRow = RequirementReference & {
  status?: Status | null;
};

export interface MetricTuningData {
  metric: MetricDetail;
  cases: MetricTuningCase[];
  run: MetricTuningRun;
}

/** Only custom metrics can be tuned; the tuning routes reject the rest. */
export function isCustomMetric(metric: MetricDetail): boolean {
  return metric.backend_type?.type_value?.toLowerCase() === 'custom';
}

export async function fetchMetricLinkedRequirements(
  factory: ApiClientFactory,
  metricId: string
): Promise<LinkedRequirementRow[]> {
  const result = await factory
    .getMetricsClient()
    .getMetricRequirements(metricId as UUID);
  // The endpoint is typed as metrics but returns the linked requirements.
  return (result as unknown as { data?: LinkedRequirementRow[] }).data ?? [];
}

/** The Tuning tab's whole state: the metric, its cases and the latest run. */
export async function fetchMetricTuning(
  factory: ApiClientFactory,
  metricId: string
): Promise<MetricTuningData> {
  const [metric, cases, run] = await Promise.all([
    factory.getMetricsClient().getMetric(metricId as UUID),
    factory.getMetricTuningClient().getTuningCases(metricId),
    factory.getMetricTuningClient().getTuningRun(metricId),
  ]);
  return { metric, cases, run };
}
