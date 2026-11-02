/**
 * Whether a metric can be tuned. The tuning routes refuse anything that is not
 * a custom metric, so callers check this before calling them.
 */
export function isTunableMetric(metric: {
  backend_type?: { type_value?: string } | null;
}): boolean {
  return metric.backend_type?.type_value?.toLowerCase() === 'custom';
}
