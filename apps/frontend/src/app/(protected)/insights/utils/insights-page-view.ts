export type InsightsPageView =
  | 'loading-endpoints'
  | 'endpoints-error'
  | 'empty-no-endpoints'
  | 'empty-no-test-results'
  | 'content';

interface ResolveInsightsPageViewInput {
  endpointsLoading: boolean;
  endpointsError: string | null;
  projectEndpointCount: number;
  endpointId: string;
  insightsLoading: boolean;
  error: string | null;
  noRuns: boolean;
}

export function resolveInsightsPageView({
  endpointsLoading,
  endpointsError,
  projectEndpointCount,
  endpointId,
  insightsLoading,
  error,
  noRuns,
}: ResolveInsightsPageViewInput): InsightsPageView {
  if (endpointsLoading) {
    return 'loading-endpoints';
  }

  if (endpointsError) {
    return 'endpoints-error';
  }

  if (projectEndpointCount === 0) {
    return 'empty-no-endpoints';
  }

  if (endpointId && !insightsLoading && !error && noRuns) {
    return 'empty-no-test-results';
  }

  return 'content';
}
