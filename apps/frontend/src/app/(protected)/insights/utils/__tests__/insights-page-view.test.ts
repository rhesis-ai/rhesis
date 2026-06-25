import { resolveInsightsPageView } from '../insights-page-view';

describe('resolveInsightsPageView', () => {
  it('returns loading-endpoints while endpoints are loading', () => {
    expect(
      resolveInsightsPageView({
        endpointsLoading: true,
        projectEndpointCount: 0,
        endpointId: '',
        insightsLoading: false,
        error: null,
        noRuns: false,
      })
    ).toBe('loading-endpoints');
  });

  it('returns empty-no-endpoints when project has no endpoints', () => {
    expect(
      resolveInsightsPageView({
        endpointsLoading: false,
        projectEndpointCount: 0,
        endpointId: '',
        insightsLoading: false,
        error: null,
        noRuns: false,
      })
    ).toBe('empty-no-endpoints');
  });

  it('returns empty-no-test-results when endpoint has no runs', () => {
    expect(
      resolveInsightsPageView({
        endpointsLoading: false,
        projectEndpointCount: 2,
        endpointId: 'ep-1',
        insightsLoading: false,
        error: null,
        noRuns: true,
      })
    ).toBe('empty-no-test-results');
  });

  it('returns content while insights are loading', () => {
    expect(
      resolveInsightsPageView({
        endpointsLoading: false,
        projectEndpointCount: 2,
        endpointId: 'ep-1',
        insightsLoading: true,
        error: null,
        noRuns: true,
      })
    ).toBe('content');
  });

  it('returns content when runs exist', () => {
    expect(
      resolveInsightsPageView({
        endpointsLoading: false,
        projectEndpointCount: 2,
        endpointId: 'ep-1',
        insightsLoading: false,
        error: null,
        noRuns: false,
      })
    ).toBe('content');
  });
});
