import { traceDrawerHref } from '../trace-links';

describe('traceDrawerHref', () => {
  it('links to the trace without a span', () => {
    expect(traceDrawerHref({ traceId: 't1', projectId: 'p1' })).toBe(
      '/traces?open_trace=t1&project_id=p1'
    );
  });

  it('adds open_span when a span is given', () => {
    expect(
      traceDrawerHref({ traceId: 't1', projectId: 'p1', spanId: 's1' })
    ).toBe('/traces?open_trace=t1&project_id=p1&open_span=s1');
  });

  it('skips an empty span id', () => {
    expect(
      traceDrawerHref({ traceId: 't1', projectId: 'p1', spanId: null })
    ).toBe('/traces?open_trace=t1&project_id=p1');
  });

  it('encodes the values', () => {
    expect(traceDrawerHref({ traceId: 'a&b', projectId: 'p 1' })).toBe(
      '/traces?open_trace=a%26b&project_id=p+1'
    );
  });
});
