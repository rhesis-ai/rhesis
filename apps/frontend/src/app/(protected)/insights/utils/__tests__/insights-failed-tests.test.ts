import {
  buildInsightsFailedTestsUrl,
  formatInsightsFailedTestsBanner,
  formatInsightsSummaryDetail,
  formatInsightsTimeRangeLabel,
  parseInsightsFailedTestsSearchParams,
} from '../insights-failed-tests';

describe('insights-failed-tests', () => {
  it('builds tests URL with insights context', () => {
    expect(
      buildInsightsFailedTestsUrl({
        endpointId: 'ep-1',
        timeRange: '1m',
      })
    ).toBe('/tests?failedFromInsights=1&endpointId=ep-1&timeRange=1m');
  });

  it('builds tests URL with behavior metric scope', () => {
    expect(
      buildInsightsFailedTestsUrl(
        { endpointId: 'ep-1', timeRange: '1m' },
        {
          behaviorId: 'beh-1',
          behaviorName: 'Safety',
          metricName: 'Toxicity',
        }
      )
    ).toBe(
      '/tests?failedFromInsights=1&endpointId=ep-1&timeRange=1m&behaviorId=beh-1&behaviorName=Safety&metric=Toxicity'
    );
  });

  it('builds tests URL with all-outcome dimension scope', () => {
    expect(
      buildInsightsFailedTestsUrl(
        { endpointId: 'ep-1', timeRange: '1m' },
        {
          behaviorId: 'beh-1',
          behaviorName: 'Safety',
          topicName: 'Claims',
          outcome: 'all',
        }
      )
    ).toBe(
      '/tests?failedFromInsights=1&endpointId=ep-1&timeRange=1m&behaviorId=beh-1&behaviorName=Safety&topic=Claims&outcome=all'
    );
  });

  it('parses insights failed tests search params', () => {
    const params = new URLSearchParams(
      'failedFromInsights=1&endpointId=ep-1&timeRange=7d&behaviorId=b1&metric=m1&topic=t1&behaviorName=Beh'
    );
    expect(parseInsightsFailedTestsSearchParams(params)).toEqual({
      endpointId: 'ep-1',
      timeRange: '7d',
      behaviorId: 'b1',
      behaviorName: 'Beh',
      metricName: 'm1',
      topicName: 't1',
      outcome: 'failed',
    });
  });

  it('returns null when query flag is missing', () => {
    const params = new URLSearchParams('endpointId=ep-1&timeRange=1m');
    expect(parseInsightsFailedTestsSearchParams(params)).toBeNull();
  });

  it('formats time range labels', () => {
    expect(formatInsightsTimeRangeLabel('1d')).toBe('1 day');
    expect(formatInsightsTimeRangeLabel('3m')).toBe('3 months');
  });

  it('formats summary detail with test results wording', () => {
    expect(formatInsightsSummaryDetail(10, 20, 10)).toBe(
      '(10/20 test results passed, 10 failed)'
    );
  });

  it('appends unique failed test case count when it differs from failures', () => {
    expect(formatInsightsSummaryDetail(10, 20, 10, 5)).toBe(
      '(10/20 test results passed, 10 failed · 5 unique test cases failed)'
    );
  });

  it('omits unique failed test case count when it matches failures', () => {
    expect(formatInsightsSummaryDetail(7, 10, 3, 3)).toBe(
      '(7/10 test results passed, 3 failed)'
    );
  });

  it('formats banner for metric drill-down', () => {
    expect(
      formatInsightsFailedTestsBanner(
        {
          endpointId: 'ep-1',
          timeRange: '1m',
          behaviorName: 'Safety',
          metricName: 'Toxicity',
        },
        3,
        'My Endpoint'
      )
    ).toContain('Toxicity');
    expect(
      formatInsightsFailedTestsBanner(
        {
          endpointId: 'ep-1',
          timeRange: '1m',
          behaviorName: 'Safety',
          metricName: 'Toxicity',
        },
        3,
        'My Endpoint'
      )
    ).toContain('3 test cases');
  });

  it('formats banner for all-outcome topic drill-down', () => {
    expect(
      formatInsightsFailedTestsBanner(
        {
          endpointId: 'ep-1',
          timeRange: '1m',
          behaviorName: 'Safety',
          topicName: 'Claims',
          outcome: 'all',
        },
        5,
        'My Endpoint'
      )
    ).toContain('for topic "Claims"');
    expect(
      formatInsightsFailedTestsBanner(
        {
          endpointId: 'ep-1',
          timeRange: '1m',
          behaviorName: 'Safety',
          metricName: 'Toxicity',
          outcome: 'all',
        },
        5,
        'My Endpoint'
      )
    ).toContain('evaluated for "Toxicity"');
  });
});
