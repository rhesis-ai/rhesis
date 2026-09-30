import {
  buildSpanQueryParams,
  buildTraceQueryParams,
  countActiveTraceDrawerFilters,
  EMPTY_TRACE_DRAWER_FILTERS,
  hasActiveTraceDrawerFilters,
  sanitizeTraceDrawerFiltersForTestRunScope,
  timeRangeToStartTimeAfter,
  type TraceDrawerFilters,
} from '../trace-filter-params';

describe('trace-filter-params', () => {
  it('builds query params from drawer filters and search', () => {
    const params = buildTraceQueryParams(
      {
        ...EMPTY_TRACE_DRAWER_FILTERS,
        projectId: 'proj-1',
        traceSource: 'test',
        timeRange: '24h',
        traceType: 'Single-Turn',
      },
      'llm.invoke'
    );

    expect(params.project_id).toBe('proj-1');
    expect(params.trace_source).toBe('test');
    expect(params.search).toBe('llm.invoke');
    expect(params.trace_type).toBe('Single-Turn');
    expect(params.start_time_after).toBeDefined();
  });

  it('omits trace type when unset', () => {
    const params = buildTraceQueryParams(EMPTY_TRACE_DRAWER_FILTERS, '');
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
      ''
    );

    expect(params.provider).toEqual(['openai', 'gemini']);
  });

  it('sends nothing when none are ticked', () => {
    expect(buildTraceQueryParams(base, '').provider).toBeUndefined();
    expect(
      buildTraceQueryParams({ ...base, providers: [] }, '').provider
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

describe('trace type filter', () => {
  const base: TraceDrawerFilters = { timeRange: 'all' };

  it('counts as one active filter', () => {
    expect(
      countActiveTraceDrawerFilters({ ...base, traceType: 'Multi-Turn' })
    ).toBe(1);
    expect(
      hasActiveTraceDrawerFilters({ ...base, traceType: 'Multi-Turn' })
    ).toBe(true);
  });

  it('is dropped when scoped to a test run', () => {
    const scoped = sanitizeTraceDrawerFiltersForTestRunScope(
      { ...base, traceType: 'Multi-Turn' },
      'run-1'
    );

    expect(scoped.traceType).toBeUndefined();
    expect(countActiveTraceDrawerFilters(scoped, { testRunScope: true })).toBe(
      0
    );
  });
});

describe('span filters', () => {
  const base: TraceDrawerFilters = { timeRange: 'all' };
  const spanOnly: TraceDrawerFilters = {
    ...base,
    spanTypes: ['tool.invoke', 'llm.invoke'],
    spanNames: ['function.visit_prep_chat'],
    isRoot: false,
  };

  it('maps span filters to repeatable span params', () => {
    const params = buildSpanQueryParams(spanOnly, ' prep ');

    expect(params.span_type).toEqual(['tool.invoke', 'llm.invoke']);
    expect(params.span_name).toEqual(['function.visit_prep_chat']);
    expect(params.is_root).toBe(false);
    expect(params.search).toBe('prep');
  });

  it('sends shared filters and the time range to the spans list', () => {
    const params = buildSpanQueryParams(
      {
        timeRange: '24h',
        projectId: 'proj-1',
        environment: 'production',
        traceSource: 'test',
        traceType: 'Multi-Turn',
        providers: ['openai'],
        testRunId: 'run-1',
      },
      ''
    );

    expect(params).toEqual(
      expect.objectContaining({
        project_id: 'proj-1',
        environment: 'production',
        trace_source: 'test',
        trace_type: 'Multi-Turn',
        provider: ['openai'],
        test_run_id: 'run-1',
      })
    );
    expect(params.start_time_after).toBeDefined();
  });

  it('leaves endpoint and evaluation out of span params', () => {
    const params = buildSpanQueryParams(
      { ...base, endpointId: 'ep-1', traceMetricsStatus: 'Fail' },
      ''
    ) as Record<string, unknown>;

    expect(params.endpoint_id).toBeUndefined();
    expect(params.trace_metrics_status).toBeUndefined();
  });

  it('sends custom time bounds', () => {
    const params = buildSpanQueryParams(
      {
        timeRange: 'custom',
        startTimeAfter: '2026-01-01T00:00:00.000Z',
        startTimeBefore: '2026-02-01T00:00:00.000Z',
      },
      ''
    );

    expect(params.start_time_after).toBe('2026-01-01T00:00:00.000Z');
    expect(params.start_time_before).toBe('2026-02-01T00:00:00.000Z');
  });

  it('leaves span filters out of trace params', () => {
    const params = buildTraceQueryParams(spanOnly, '') as Record<
      string,
      unknown
    >;

    expect(params.span_type).toBeUndefined();
    expect(params.is_root).toBeUndefined();
  });

  it('counts each span section once, in the spans view only', () => {
    expect(countActiveTraceDrawerFilters(spanOnly, { view: 'spans' })).toBe(3);
    expect(countActiveTraceDrawerFilters(spanOnly)).toBe(0);
    expect(hasActiveTraceDrawerFilters(spanOnly)).toBe(false);
  });

  it('counts root=true as active', () => {
    expect(
      hasActiveTraceDrawerFilters({ ...base, isRoot: true }, { view: 'spans' })
    ).toBe(true);
  });

  it('does not count trace-only filters in the spans view', () => {
    const traceOnly = {
      ...base,
      endpointId: 'ep-1',
      traceMetricsStatus: 'Fail',
    };

    expect(countActiveTraceDrawerFilters(traceOnly)).toBe(2);
    expect(countActiveTraceDrawerFilters(traceOnly, { view: 'spans' })).toBe(0);
    expect(
      countActiveTraceDrawerFilters(traceOnly, {
        view: 'spans',
        testRunScope: true,
      })
    ).toBe(0);
  });

  it('survives being scoped to a test run', () => {
    const scoped = sanitizeTraceDrawerFiltersForTestRunScope(spanOnly, 'run-1');

    expect(scoped.spanTypes).toEqual(spanOnly.spanTypes);
    expect(scoped.spanNames).toEqual(spanOnly.spanNames);
    expect(scoped.isRoot).toBe(false);
    expect(
      countActiveTraceDrawerFilters(scoped, {
        testRunScope: true,
        view: 'spans',
      })
    ).toBe(3);
  });
});
