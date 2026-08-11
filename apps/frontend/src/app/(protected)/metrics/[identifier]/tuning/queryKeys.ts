/**
 * Query keys local to the experimental metric tuning tab.
 *
 * Deliberately not added to `src/constants/query-keys.ts` — keeping them here
 * means removing the feature is a folder delete.
 */
export const metricTuningKeys = {
  all: () => ['metric-tuning'] as const,
  cases: (metricId: string) => ['metric-tuning', metricId, 'cases'] as const,
};
