import type { SpanNode } from '@/utils/api-client/interfaces/telemetry';

type MetricEntry = {
  is_successful?: boolean;
  override?: { original_value?: boolean };
};

/**
 * The automated verdict for a span, counted across both metric sections.
 *
 * Deliberately the automated result and not the span's current outcome: it
 * sits beside the human verdict so the difference is visible, and
 * `displayStatusOf` already folds the annotation in, which would make the two
 * sides always agree. Each metric is read at `override.original_value` when an
 * annotation has already flipped it.
 */
export function automatedVerdictFor(span: SpanNode) {
  const traceMetrics = span.trace_metrics as Record<
    string,
    Record<string, unknown>
  > | null;
  if (!traceMetrics) return null;

  let total = 0;
  let passed = 0;
  for (const section of ['turn_metrics', 'conversation_metrics']) {
    const sectionData = traceMetrics[section] as
      | Record<string, unknown>
      | undefined;
    const metrics = (sectionData?.metrics ?? {}) as Record<string, MetricEntry>;
    for (const metric of Object.values(metrics)) {
      total++;
      if (metric.override?.original_value ?? metric.is_successful) passed++;
    }
  }

  // No metric ran, so there is no automated verdict to show or to conflict with.
  if (total === 0) return null;
  const allPassed = passed === total;
  return {
    passed: allPassed,
    label: allPassed ? 'Passed' : 'Failed',
    count: `${passed}/${total}`,
    failed: total - passed,
  };
}
