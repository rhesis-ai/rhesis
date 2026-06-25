import { resolveInsightsPageView } from '../insights-page-view';

const baseInput = {
  endpointsLoading: false,
  endpointsError: null,
  projectEndpointCount: 2,
  endpointId: 'ep-1',
  insightsLoading: false,
  error: null,
  noRuns: false,
};

describe('resolveInsightsPageView', () => {
  it('returns loading-endpoints while endpoints are loading', () => {
    expect(
      resolveInsightsPageView({
        ...baseInput,
        endpointsLoading: true,
      })
    ).toBe('loading-endpoints');
  });

  it('returns endpoints-error when endpoints fetch failed', () => {
    expect(
      resolveInsightsPageView({
        ...baseInput,
        endpointsError: 'Failed to load endpoints. Please try again.',
        projectEndpointCount: 0,
      })
    ).toBe('endpoints-error');
  });

  it('returns empty-no-endpoints when project has no endpoints', () => {
    expect(
      resolveInsightsPageView({
        ...baseInput,
        projectEndpointCount: 0,
        endpointId: '',
      })
    ).toBe('empty-no-endpoints');
  });

  it('returns empty-no-test-results when endpoint has no runs', () => {
    expect(
      resolveInsightsPageView({
        ...baseInput,
        noRuns: true,
      })
    ).toBe('empty-no-test-results');
  });

  it('returns content while insights are loading', () => {
    expect(
      resolveInsightsPageView({
        ...baseInput,
        insightsLoading: true,
        noRuns: true,
      })
    ).toBe('content');
  });

  it('returns content when runs exist', () => {
    expect(resolveInsightsPageView(baseInput)).toBe('content');
  });
});
