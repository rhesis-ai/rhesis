import {
  buildTraceQueryParams,
  EMPTY_TRACE_DRAWER_FILTERS,
  hasActiveTraceDrawerFilters,
  timeRangeToStartTimeAfter,
} from '../trace-filter-params';

describe('trace-filter-params', () => {
  it('builds query params from drawer, search, and type filter', () => {
    const params = buildTraceQueryParams(
      {
        ...EMPTY_TRACE_DRAWER_FILTERS,
        projectId: 'proj-1',
        traceSource: 'test',
        timeRange: '24h',
      },
      'llm.invoke',
      'Single-Turn',
      50,
      0
    );

    expect(params.project_id).toBe('proj-1');
    expect(params.trace_source).toBe('test');
    expect(params.search).toBe('llm.invoke');
    expect(params.trace_type).toBe('Single-Turn');
    expect(params.start_time_after).toBeDefined();
    expect(params.limit).toBe(50);
    expect(params.offset).toBe(0);
  });

  it('omits type filter when all', () => {
    const params = buildTraceQueryParams(
      EMPTY_TRACE_DRAWER_FILTERS,
      '',
      'all',
      25,
      50
    );
    expect(params.trace_type).toBeUndefined();
    expect(params.offset).toBe(50);
  });

  it('detects active drawer filters', () => {
    expect(hasActiveTraceDrawerFilters(EMPTY_TRACE_DRAWER_FILTERS)).toBe(false);
    expect(
      hasActiveTraceDrawerFilters({
        ...EMPTY_TRACE_DRAWER_FILTERS,
        environment: 'production',
      })
    ).toBe(true);
    expect(
      hasActiveTraceDrawerFilters({
        ...EMPTY_TRACE_DRAWER_FILTERS,
        timeRange: '7d',
      })
    ).toBe(true);
  });

  it('detects active drawer filters in test run scope', () => {
    expect(
      hasActiveTraceDrawerFilters(
        {
          ...EMPTY_TRACE_DRAWER_FILTERS,
          testRunId: 'run-1',
          projectId: 'proj-1',
        },
        { testRunScope: true }
      )
    ).toBe(false);
    expect(
      hasActiveTraceDrawerFilters(
        {
          ...EMPTY_TRACE_DRAWER_FILTERS,
          testRunId: 'run-1',
          traceMetricsStatus: 'pass',
        },
        { testRunScope: true }
      )
    ).toBe(true);
  });

  it('maps preset time ranges to ISO timestamps', () => {
    const after = timeRangeToStartTimeAfter('24h');
    expect(after).toBeDefined();
    if (!after) return;
    const diff = Date.now() - new Date(after).getTime();
    expect(diff).toBeGreaterThan(23 * 60 * 60 * 1000);
    expect(diff).toBeLessThan(25 * 60 * 60 * 1000);
  });
});
