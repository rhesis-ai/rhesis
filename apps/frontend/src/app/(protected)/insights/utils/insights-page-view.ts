export type InsightsPageView =
  | 'loading-endpoints'
  | 'empty-no-endpoints'
  | 'empty-no-test-results'
  | 'content';

interface ResolveInsightsPageViewInput {
  endpointsLoading: boolean;
  projectEndpointCount: number;
  endpointId: string;
  insightsLoading: boolean;
  error: string | null;
  noRuns: boolean;
}

export function resolveInsightsPageView({
  endpointsLoading,
  projectEndpointCount,
  endpointId,
  insightsLoading,
  error,
  noRuns,
}: ResolveInsightsPageViewInput): InsightsPageView {
  if (endpointsLoading) {
    return 'loading-endpoints';
  }

  if (projectEndpointCount === 0) {
    return 'empty-no-endpoints';
  }

  if (endpointId && !insightsLoading && !error && noRuns) {
    return 'empty-no-test-results';
  }

  return 'content';
}
