import {
  filtersFromSearchParams,
  hasTraceUrlFilters,
  viewFromSearchParams,
  withTraceUrlState,
} from '../trace-url-state';
import {
  EMPTY_TRACE_DRAWER_FILTERS,
  type TraceDrawerFilters,
} from '../trace-filter-params';

const full: TraceDrawerFilters = {
  timeRange: '7d',
  projectId: 'proj-1',
  endpointId: 'ep-1',
  environment: 'production',
  traceSource: 'operation',
  traceMetricsStatus: 'Fail',
  providers: ['openai', 'gemini'],
  testRunId: 'run-1',
  testResultId: 'result-1',
  testId: 'test-1',
  traceType: 'Multi-Turn',
  spanTypes: ['tool.invoke', 'span'],
  spanNames: ['function.visit_prep_chat'],
  isRoot: false,
};

describe('trace URL state', () => {
  it('round-trips every filter and the view', () => {
    const params = withTraceUrlState(new URLSearchParams(), 'spans', full);

    expect(viewFromSearchParams(params)).toBe('spans');
    expect(filtersFromSearchParams(params)).toEqual(full);
  });

  it('writes nothing for the default state', () => {
    const params = withTraceUrlState(
      new URLSearchParams(),
      'traces',
      EMPTY_TRACE_DRAWER_FILTERS
    );

    expect(params.toString()).toBe('');
    expect(filtersFromSearchParams(params)).toEqual(EMPTY_TRACE_DRAWER_FILTERS);
  });

  it('stores a preset range as its token, not a timestamp', () => {
    const params = withTraceUrlState(new URLSearchParams(), 'traces', {
      timeRange: '24h',
      // Left over from a custom range; meaningless with a preset.
      startTimeAfter: '2026-01-01T00:00:00.000Z',
    });

    expect(params.get('time')).toBe('24h');
    expect(params.has('start_time_after')).toBe(false);
  });

  it('keeps custom bounds', () => {
    const custom: TraceDrawerFilters = {
      timeRange: 'custom',
      startTimeAfter: '2026-01-01T00:00:00.000Z',
      startTimeBefore: '2026-02-01T00:00:00.000Z',
    };
    const params = withTraceUrlState(new URLSearchParams(), 'traces', custom);

    expect(filtersFromSearchParams(params)).toEqual(custom);
  });

  it('keeps params it does not own and replaces stale ones', () => {
    const current = new URLSearchParams(
      'open_trace=t1&open_span=s1&view=spans&span_type=tool.invoke'
    );
    const params = withTraceUrlState(current, 'traces', {
      timeRange: 'all',
      environment: 'staging',
    });

    expect(params.get('open_trace')).toBe('t1');
    expect(params.get('open_span')).toBe('s1');
    expect(params.has('view')).toBe(false);
    expect(params.has('span_type')).toBe(false);
    expect(params.get('environment')).toBe('staging');
  });

  it('drops values that do not parse', () => {
    const filters = filtersFromSearchParams(
      new URLSearchParams(
        'time=forever&source=nope&evaluation=Maybe&turns=Three&root=yes' +
          '&view=graph'
      )
    );

    expect(filters).toEqual(EMPTY_TRACE_DRAWER_FILTERS);
    expect(viewFromSearchParams(new URLSearchParams('view=graph'))).toBe(
      'traces'
    );
  });

  it('drops a custom bound that is not a date', () => {
    const filters = filtersFromSearchParams(
      new URLSearchParams('time=custom&start_time_after=soon')
    );

    expect(filters).toEqual({ timeRange: 'custom' });
  });

  it('reads root=true', () => {
    expect(
      filtersFromSearchParams(new URLSearchParams('root=true')).isRoot
    ).toBe(true);
  });

  it('treats a project alone as unfiltered for the prefetch', () => {
    expect(hasTraceUrlFilters(new URLSearchParams('project_id=p1'))).toBe(
      false
    );
    expect(
      hasTraceUrlFilters(new URLSearchParams('project_id=p1&time=7d'))
    ).toBe(true);
    expect(hasTraceUrlFilters(new URLSearchParams('open_trace=t1'))).toBe(
      false
    );
  });
});
