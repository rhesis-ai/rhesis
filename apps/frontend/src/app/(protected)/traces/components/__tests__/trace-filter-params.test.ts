import {
  buildTraceQueryParams,
  countActiveTraceDrawerFilters,
  EMPTY_TRACE_DRAWER_FILTERS,
  hasActiveTraceDrawerFilters,
  sanitizeTraceDrawerFiltersForTestRunScope,
  timeRangeToStartTimeAfter,
  type TraceDrawerFilters,
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
      'Single-Turn'
    );

    expect(params.project_id).toBe('proj-1');
    expect(params.trace_source).toBe('test');
    expect(params.search).toBe('llm.invoke');
    expect(params.trace_type).toBe('Single-Turn');
    expect(params.start_time_after).toBeDefined();
  });

  it('omits type filter when all', () => {
    const params = buildTraceQueryParams(EMPTY_TRACE_DRAWER_FILTERS, '', 'all');
    expect(params.trace_type).toBeUndefined();
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

describe('provider filter', () => {
  const base: TraceDrawerFilters = { timeRange: 'all' };

  it('sends every ticked provider as a repeatable param', () => {
    const params = buildTraceQueryParams(
      { ...base, providers: ['openai', 'gemini'] },
      '',
      'all'
    );

    expect(params.provider).toEqual(['openai', 'gemini']);
  });

  it('sends nothing when none are ticked', () => {
    expect(buildTraceQueryParams(base, '', 'all').provider).toBeUndefined();
    expect(
      buildTraceQueryParams({ ...base, providers: [] }, '', 'all').provider
    ).toBeUndefined();
  });

  it('counts as one active filter however many are ticked', () => {
    // It is one section in the drawer, so it reads as one filter in the badge.
    expect(
      countActiveTraceDrawerFilters({ ...base, providers: ['openai'] })
    ).toBe(1);
    expect(
      countActiveTraceDrawerFilters({
        ...base,
        providers: ['openai', 'gemini', 'azure'],
      })
    ).toBe(1);
  });

  it('counts as none when the list is empty', () => {
    expect(countActiveTraceDrawerFilters({ ...base, providers: [] })).toBe(0);
  });

  it('marks the drawer as filtered', () => {
    expect(
      hasActiveTraceDrawerFilters({ ...base, providers: ['openai'] })
    ).toBe(true);
    expect(hasActiveTraceDrawerFilters({ ...base, providers: [] })).toBe(false);
  });

  it('survives being scoped to a test run', () => {
    // One run can span several providers, so narrowing inside it is still useful.
    const scoped = sanitizeTraceDrawerFiltersForTestRunScope(
      { ...base, providers: ['openai'], projectId: 'gone' },
      'run-1'
    );

    expect(scoped.providers).toEqual(['openai']);
    expect(scoped.projectId).toBeUndefined();
    expect(countActiveTraceDrawerFilters(scoped, { testRunScope: true })).toBe(
      1
    );
  });
});
