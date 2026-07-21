import {
  buildInsightsFailedTestsUrl,
  formatInsightsFailedTestsBanner,
  formatInsightsRunFilterLabel,
  formatInsightsSummaryDetail,
  formatInsightsTimeRangeLabel,
  parseInsightsFailedTestsSearchParams,
} from '../insights-failed-tests';

describe('insights-failed-tests', () => {
  it('builds tests URL with time range scope', () => {
    expect(
      buildInsightsFailedTestsUrl({
        endpointId: 'ep-1',
        runFilterMode: 'timeRange',
        timeRange: '1m',
        testRunIds: [],
      })
    ).toBe(
      '/tests?failedFromInsights=1&endpointId=ep-1&runFilterMode=timeRange&timeRange=1m'
    );
  });

  it('builds tests URL with custom test run scope', () => {
    expect(
      buildInsightsFailedTestsUrl({
        endpointId: 'ep-1',
        runFilterMode: 'testRuns',
        timeRange: '1m',
        testRunIds: ['run-1', 'run-2'],
      })
    ).toBe(
      '/tests?failedFromInsights=1&endpointId=ep-1&runFilterMode=testRuns&testRunIds=run-1%2Crun-2'
    );
  });

  it('builds tests URL for all test runs with an empty testRunIds param', () => {
    expect(
      buildInsightsFailedTestsUrl({
        endpointId: 'ep-1',
        runFilterMode: 'testRuns',
        timeRange: '1m',
        testRunIds: [],
      })
    ).toBe(
      '/tests?failedFromInsights=1&endpointId=ep-1&runFilterMode=testRuns&testRunIds='
    );
  });

  it('parses all-runs testRuns URLs with empty testRunIds', () => {
    const params = new URLSearchParams(
      'failedFromInsights=1&endpointId=ep-1&runFilterMode=testRuns&testRunIds='
    );
    expect(parseInsightsFailedTestsSearchParams(params)).toEqual({
      endpointId: 'ep-1',
      runFilterMode: 'testRuns',
      timeRange: '1m',
      testRunIds: [],
      outcome: 'failed',
    });
  });

  it('builds tests URL with behavior metric scope', () => {
    expect(
      buildInsightsFailedTestsUrl(
        {
          endpointId: 'ep-1',
          runFilterMode: 'timeRange',
          timeRange: '1m',
          testRunIds: [],
        },
        {
          behaviorId: 'beh-1',
          behaviorName: 'Safety',
          metricName: 'Toxicity',
        }
      )
    ).toBe(
      '/tests?failedFromInsights=1&endpointId=ep-1&runFilterMode=timeRange&timeRange=1m&behaviorId=beh-1&behaviorName=Safety&metric=Toxicity'
    );
  });

  it('builds tests URL with all-outcome dimension scope', () => {
    expect(
      buildInsightsFailedTestsUrl(
        {
          endpointId: 'ep-1',
          runFilterMode: 'timeRange',
          timeRange: '1m',
          testRunIds: [],
        },
        {
          behaviorId: 'beh-1',
          behaviorName: 'Safety',
          topicName: 'Claims',
          outcome: 'all',
        }
      )
    ).toBe(
      '/tests?failedFromInsights=1&endpointId=ep-1&runFilterMode=timeRange&timeRange=1m&behaviorId=beh-1&behaviorName=Safety&topic=Claims&outcome=all'
    );
  });

  it('parses insights failed tests search params', () => {
    const params = new URLSearchParams(
      'failedFromInsights=1&endpointId=ep-1&runFilterMode=testRuns&testRunIds=run-1,run-2&behaviorId=b1&metric=m1&topic=t1&behaviorName=Beh'
    );
    expect(parseInsightsFailedTestsSearchParams(params)).toEqual({
      endpointId: 'ep-1',
      runFilterMode: 'testRuns',
      timeRange: '1m',
      testRunIds: ['run-1', 'run-2'],
      behaviorId: 'b1',
      behaviorName: 'Beh',
      metricName: 'm1',
      topicName: 't1',
      outcome: 'failed',
    });
  });

  it('parses legacy timeRange URLs as time range mode', () => {
    const params = new URLSearchParams(
      'failedFromInsights=1&endpointId=ep-1&timeRange=7d'
    );
    expect(parseInsightsFailedTestsSearchParams(params)).toEqual({
      endpointId: 'ep-1',
      runFilterMode: 'timeRange',
      timeRange: '7d',
      testRunIds: [],
      outcome: 'failed',
    });
  });

  it('returns null when query flag is missing', () => {
    const params = new URLSearchParams(
      'endpointId=ep-1&runFilterMode=timeRange&timeRange=1m'
    );
    expect(parseInsightsFailedTestsSearchParams(params)).toBeNull();
  });

  it('formats run filter labels', () => {
    expect(
      formatInsightsRunFilterLabel({
        runFilterMode: 'timeRange',
        timeRange: '1m',
        testRunIds: [],
      })
    ).toBe('the last 1 month');
    expect(
      formatInsightsRunFilterLabel({
        runFilterMode: 'testRuns',
        timeRange: '1m',
        testRunIds: [],
      })
    ).toBe('all test runs');
    expect(formatInsightsTimeRangeLabel('1d')).toBe('1 day');
  });

  it('formats summary detail with test results wording', () => {
    expect(formatInsightsSummaryDetail(10, 20, 10)).toBe(
      '(10/20 test results passed, 10 failed)'
    );
  });

  it('formats banner for metric drill-down', () => {
    expect(
      formatInsightsFailedTestsBanner(
        {
          endpointId: 'ep-1',
          runFilterMode: 'timeRange',
          timeRange: '1m',
          testRunIds: [],
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
          runFilterMode: 'timeRange',
          timeRange: '1m',
          testRunIds: [],
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
          runFilterMode: 'timeRange',
          timeRange: '1m',
          testRunIds: [],
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
          runFilterMode: 'testRuns',
          timeRange: '1m',
          testRunIds: ['run-1'],
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
