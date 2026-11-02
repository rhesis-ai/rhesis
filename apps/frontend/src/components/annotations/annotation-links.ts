import type { Annotation } from '@/utils/api-client/interfaces/annotation';

/**
 * Where an annotation was left, as an app URL, or null when its context does
 * not say enough to get there.
 */
export function annotationEntityUrl(
  row: Pick<Annotation, 'entity_type' | 'entity_id' | 'context'>
): string | null {
  const ctx = row.context;
  if (row.entity_type === 'TestResult' && ctx?.test_run_id) {
    return (
      `/test-runs/${encodeURIComponent(ctx.test_run_id)}` +
      `?selectedresult=${encodeURIComponent(ctx.test_result_id ?? row.entity_id)}` +
      `&detailTab=annotations`
    );
  }
  if (row.entity_type === 'Trace' && ctx?.trace_id && ctx?.project_id) {
    return (
      `/traces?open_trace=${encodeURIComponent(ctx.trace_id)}` +
      `&project_id=${encodeURIComponent(ctx.project_id)}`
    );
  }
  if (row.entity_type === 'Test') {
    // Two kinds of annotated test, reached two different ways: a metric's
    // tuning case through the metric that owns it, an explorer test through
    // its test set. `metric_id` is what tells them apart.
    if (ctx?.metric_id) {
      return `/metrics/${encodeURIComponent(ctx.metric_id)}?tab=tuning`;
    }
    if (ctx?.test_set_id) {
      return (
        `/explorer/${encodeURIComponent(ctx.test_set_id)}` +
        `?test=${encodeURIComponent(row.entity_id)}`
      );
    }
  }
  return null;
}
