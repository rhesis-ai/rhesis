import type { MetricTarget } from '@/utils/api-client/interfaces/metric';
import {
  FROM_METRIC_PARAM,
  targetTraceFilters,
  tracesHrefForTarget,
  unappliedRefinements,
  withoutTargetFilters,
} from '../target-filters';
import {
  filtersFromSearchParams,
  viewFromSearchParams,
} from '../trace-url-state';

const CHOICES = [
  { on: 'turn' },
  { on: 'conversation' },
  { on: 'run' },
  { on: 'tool_call', span_kind: 'tool.invoke' },
  { on: 'retrieval', span_kind: 'retrieval' },
  { on: 'model_call', span_kind: 'llm.invoke' },
  { on: 'agent', span_kind: 'agent.invoke' },
];

function opened(href: string) {
  const params = new URLSearchParams(href.split('?')[1] ?? '');
  return {
    view: viewFromSearchParams(params),
    filters: filtersFromSearchParams(params),
    fromMetric: params.get(FROM_METRIC_PARAM),
  };
}

describe('targetTraceFilters', () => {
  it.each([
    [
      { on: 'tool_call', name: 'issue_refund' },
      { spanTypes: ['tool.invoke'], tools: ['issue_refund'] },
    ],
    [
      { on: 'model_call', name: 'gpt-4.1' },
      { spanTypes: ['llm.invoke'], models: ['gpt-4.1'] },
    ],
    [
      { on: 'agent', name: 'billing_agent' },
      { spanTypes: ['agent.invoke'], agents: ['billing_agent'] },
    ],
    [
      { on: 'retrieval', name: 'kb_search' },
      { spanTypes: ['retrieval'], spanNames: ['kb_search'] },
    ],
    [{ on: 'tool_call' }, { spanTypes: ['tool.invoke'] }],
  ])('opens the spans of a per-span target %o', (target, filters) => {
    expect(targetTraceFilters(target, CHOICES)).toEqual({
      view: 'spans',
      filters,
    });
  });

  it('opens the root spans for each turn', () => {
    expect(targetTraceFilters({ on: 'turn' }, CHOICES)).toEqual({
      view: 'spans',
      filters: { isRoot: true },
    });
  });

  it('opens multi-turn traces for the conversation and every trace for the run', () => {
    expect(targetTraceFilters({ on: 'conversation' }, CHOICES)).toEqual({
      view: 'traces',
      filters: { traceType: 'Multi-Turn' },
    });
    expect(targetTraceFilters({ on: 'run' }, CHOICES)).toEqual({
      view: 'traces',
      filters: {},
    });
  });
});

describe('tracesHrefForTarget', () => {
  it('writes the filters the Traces page reads back', () => {
    const href = tracesHrefForTarget(
      { on: 'tool_call', name: 'issue_refund' },
      CHOICES,
      'metric-1'
    );

    expect(href.startsWith('/traces?')).toBe(true);
    expect(opened(href)).toEqual({
      view: 'spans',
      filters: {
        timeRange: 'all',
        spanTypes: ['tool.invoke'],
        tools: ['issue_refund'],
      },
      fromMetric: 'metric-1',
    });
  });

  it('round-trips a turn and the conversation', () => {
    expect(
      opened(tracesHrefForTarget({ on: 'turn' }, CHOICES)).filters
    ).toEqual({
      timeRange: 'all',
      isRoot: true,
    });
    expect(
      opened(tracesHrefForTarget({ on: 'conversation' }, CHOICES)).filters
    ).toEqual({ timeRange: 'all', traceType: 'Multi-Turn' });
  });

  it('links to every trace for the run', () => {
    expect(tracesHrefForTarget({ on: 'run' }, CHOICES)).toBe('/traces');
  });
});

describe('withoutTargetFilters', () => {
  it('removes only what the target set', () => {
    const current = {
      timeRange: '7d' as const,
      spanTypes: ['tool.invoke', 'retrieval'],
      tools: ['issue_refund'],
      environment: 'production',
    };

    expect(
      withoutTargetFilters(current, {
        spanTypes: ['tool.invoke'],
        tools: ['issue_refund'],
      })
    ).toEqual({
      timeRange: '7d',
      spanTypes: ['retrieval'],
      environment: 'production',
    });
  });

  it('clears a single value the target set', () => {
    expect(
      withoutTargetFilters({ timeRange: 'all', isRoot: true }, { isRoot: true })
    ).toEqual({ timeRange: 'all' });
  });
});

describe('unappliedRefinements', () => {
  it('names the agent and attributes the Traces filters leave out', () => {
    expect(
      unappliedRefinements({
        within: 'billing_agent',
        where: {
          'rhesis.reported.metadata.channel': 'web',
          'app.customer_tier': ['gold', 'silver'],
        },
      })
    ).toEqual([
      'inside billing_agent',
      'rhesis.reported.metadata.channel is web',
      'app.customer_tier is one of gold, silver',
    ]);
  });

  it('is empty when every part of the target applies', () => {
    expect(unappliedRefinements({})).toEqual([]);
  });

  it('still opens the spans of the target kind and name', () => {
    const target: MetricTarget = {
      on: 'tool_call',
      name: 'issue_refund',
      within: 'billing_agent',
    };

    expect(targetTraceFilters(target, CHOICES).filters).toEqual({
      spanTypes: ['tool.invoke'],
      tools: ['issue_refund'],
    });
  });
});
