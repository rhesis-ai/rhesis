/** Metric type values, matching the backend's `MetricType` lookups. */
export const METRIC_TYPES = {
  CUSTOM_PROMPT: 'custom-prompt',
  API_CALL: 'api-call',
  CUSTOM_CODE: 'custom-code',
  GRADING: 'grading',
  FRAMEWORK: 'framework',
  RULE: 'rule',
} as const;

export type MetricTypeValue = (typeof METRIC_TYPES)[keyof typeof METRIC_TYPES];

/** How the metrics list and its filters name each metric type. */
export const METRIC_TYPE_LABELS: Record<MetricTypeValue, string> = {
  [METRIC_TYPES.CUSTOM_PROMPT]: 'LLM Judge',
  [METRIC_TYPES.API_CALL]: 'External API',
  [METRIC_TYPES.CUSTOM_CODE]: 'Script',
  [METRIC_TYPES.GRADING]: 'Grades',
  [METRIC_TYPES.FRAMEWORK]: 'Framework',
  [METRIC_TYPES.RULE]: 'Rule',
};

export function isRuleMetric(metric: {
  metric_type?: { type_value?: string | null } | null;
}): boolean {
  return metric.metric_type?.type_value === METRIC_TYPES.RULE;
}
