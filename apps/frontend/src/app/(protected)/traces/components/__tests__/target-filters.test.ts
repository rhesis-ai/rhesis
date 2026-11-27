import type { MetricTarget } from '@/utils/api-client/interfaces/metric';
import {
  FROM_METRIC_PARAM,
  tracesHrefForTarget,
  withoutTargetFilter,
} from '../target-filters';
import { buildSpanQueryParams } from '../trace-filter-params';
import {
  filtersFromSearchParams,
  viewFromSearchParams,
  withTraceUrlState,
} from '../trace-url-state';

function opened(href: string) {
  const params = new URLSearchParams(href.split('?')[1] ?? '');
  return {
    view: viewFromSearchParams(params),
    filters: filtersFromSearchParams(params),
    fromMetric: params.get(FROM_METRIC_PARAM),
  };
}

const REFUNDS: MetricTarget = {
  on: 'span',
  where: [
    { field: 'kind', op: '==', value: 'tool.invoke' },
    {
      field: 'ai.tool.name',
      op: 'in',
      value: ['issue_refund', 'cancel_order'],
    },
    { field: 'app.channel', op: '!=', value: 'internal' },
  ],
  within: 'billing_agent',
};

describe('tracesHrefForTarget', () => {
  it('opens the spans view with the target itself as the filter', () => {
    const href = tracesHrefForTarget(REFUNDS, 'metric-1');

    expect(href.startsWith('/traces?')).toBe(true);
    const { view, filters, fromMetric } = opened(href);
    expect(view).toBe('spans');
    expect(fromMetric).toBe('metric-1');
    expect(JSON.parse(filters.target ?? '')).toEqual(REFUNDS);
  });

  it.each([{ on: 'turn' }, { on: 'conversation' }, { on: 'run' }])(
    'passes %o as a target too, since the API matches every kind exactly',
    target => {
      const { view, filters } = opened(tracesHrefForTarget(target));
      expect(view).toBe('spans');
      expect(JSON.parse(filters.target ?? '')).toEqual(target);
    }
  );

  it('no longer writes the old tool and span type filters', () => {
    const { filters } = opened(
      tracesHrefForTarget({ on: 'tool_call', name: 'issue_refund' })
    );
    expect(filters.tools).toBeUndefined();
    expect(filters.spanTypes).toBeUndefined();
  });

  it('sends the target on to the spans endpoint, URL-encoded', () => {
    const { filters } = opened(tracesHrefForTarget(REFUNDS));
    const params = buildSpanQueryParams(filters, '');
    expect(params.target).toBe(JSON.stringify(REFUNDS));
  });
});

describe('old links', () => {
  it('still read the TBE 4 tool and span type filters', () => {
    const { view, filters, fromMetric } = opened(
      '/traces?view=spans&span_type=tool.invoke&tool=issue_refund&from_metric=metric-1'
    );
    expect(view).toBe('spans');
    expect(filters).toEqual({
      timeRange: 'all',
      spanTypes: ['tool.invoke'],
      tools: ['issue_refund'],
    });
    expect(fromMetric).toBe('metric-1');
  });

  it.each([
    '{"on":"span","where":[null]}',
    '{"on":"span","where":"kind"}',
    '{"on":"span","where":[{"op":"==","value":"x"}]}',
    '{"on":"span","where":{"channel":{"a":1}}}',
    '{"on":"tool_call","name":["x"]}',
  ])('drop a malformed target (%s) instead of drawing or sending it', raw => {
    const params = new URLSearchParams();
    params.set('view', 'spans');
    params.set('target', raw);
    expect(filtersFromSearchParams(params).target).toBeUndefined();
  });

  it.each(['not json', '[1,2]', '{"name":"x"}', '%7B'])(
    'drop a target that is not a JSON target (%s) instead of sending it',
    raw => {
      const params = new URLSearchParams();
      params.set('view', 'spans');
      params.set('target', raw);
      expect(filtersFromSearchParams(params).target).toBeUndefined();
    }
  );
});

describe('withoutTargetFilter', () => {
  it('removes the target and keeps what the user added', () => {
    expect(
      withoutTargetFilter({
        timeRange: '7d',
        environment: 'production',
        target: JSON.stringify(REFUNDS),
      })
    ).toEqual({ timeRange: '7d', environment: 'production' });
  });

  it('writes no target back to the URL once removed', () => {
    const params = withTraceUrlState(
      new URLSearchParams('target=x&view=spans'),
      'spans',
      withoutTargetFilter({ timeRange: 'all', target: '{"on":"turn"}' })
    );
    expect(params.has('target')).toBe(false);
  });
});
