import { render } from '@testing-library/react';
import {
  formatMetricTarget,
  getMetricTargetIcon,
  isTargetOnValue,
  isTargetShape,
  metricRunsOnTestType,
  offeredTargets,
  offeredTargetsWithCustom,
  SPAN_TARGET_CHOICE,
  targetConditions,
  targetSpanKind,
} from '../metric-targets';
import type {
  MetricTarget,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';

const CHOICES: MetricTargetChoice[] = [
  { on: 'turn', label: 'Each turn', description: '', per_span: false },
  {
    on: 'conversation',
    label: 'The conversation',
    description: '',
    per_span: false,
  },
  {
    on: 'tool_call',
    label: 'Each tool call',
    description: '',
    per_span: true,
    span_kind: 'tool.invoke',
  },
];

describe('metricRunsOnTestType', () => {
  const conversation = { config: { target: { on: 'conversation' } } };
  const turn = { config: { target: { on: 'turn' } } };

  it('leaves conversation metrics out of single-turn tests', () => {
    expect(metricRunsOnTestType(conversation, 'Single-Turn')).toBe(false);
    expect(metricRunsOnTestType(turn, 'Single-Turn')).toBe(true);
  });

  it('runs every metric on multi-turn tests or when the type is unknown', () => {
    expect(metricRunsOnTestType(conversation, 'Multi-Turn')).toBe(true);
    expect(metricRunsOnTestType(conversation, undefined)).toBe(true);
  });

  it('leaves metrics needing a reference answer out of multi-turn tests', () => {
    const reference = { ...turn, ground_truth_required: true };
    expect(metricRunsOnTestType(reference, 'Multi-Turn')).toBe(false);
    expect(metricRunsOnTestType(reference, 'Single-Turn')).toBe(true);
  });
});

describe('formatMetricTarget', () => {
  it('uses the registry label and adds the name', () => {
    expect(formatMetricTarget({ on: 'turn' }, CHOICES)).toBe('Each turn');
    expect(
      formatMetricTarget({ on: 'tool_call', name: 'search' }, CHOICES)
    ).toBe('Each tool call (search)');
  });

  it('names custom spans, which the registry does not list', () => {
    expect(formatMetricTarget({ on: 'span' }, CHOICES)).toBe('Custom spans');
  });

  it('falls back to the raw value before the registry loads', () => {
    expect(formatMetricTarget({ on: 'agent' }, undefined)).toBe('agent');
  });
});

describe('offeredTargets', () => {
  it('narrows to supported targets, keeping registry order', () => {
    expect(
      offeredTargets(CHOICES, { supported: ['tool_call', 'turn'] }).map(
        c => c.on
      )
    ).toEqual(['turn', 'tool_call']);
  });

  it('offers everything when supported targets are unknown', () => {
    expect(offeredTargets(CHOICES, { supported: null })).toHaveLength(3);
  });

  it('drops per-span and conversation targets when a reference answer is required', () => {
    expect(
      offeredTargets(CHOICES, { groundTruthRequired: true }).map(c => c.on)
    ).toEqual(['turn']);
  });
});

describe('offeredTargetsWithCustom', () => {
  it('adds custom spans when the metric supports span', () => {
    expect(
      offeredTargetsWithCustom(CHOICES, {
        supported: ['turn', 'tool_call', 'span'],
      }).map(c => c.on)
    ).toEqual(['turn', 'tool_call', 'span']);
  });

  it('leaves it out when the metric does not', () => {
    expect(
      offeredTargetsWithCustom(CHOICES, { supported: ['turn', 'tool_call'] })
    ).not.toContain(SPAN_TARGET_CHOICE);
  });

  it('offers it with unknown support only when a per-span preset is offered', () => {
    expect(offeredTargetsWithCustom(CHOICES).at(-1)).toBe(SPAN_TARGET_CHOICE);
    expect(
      offeredTargetsWithCustom(CHOICES, { groundTruthRequired: true })
    ).not.toContain(SPAN_TARGET_CHOICE);
  });
});

describe('targetConditions', () => {
  it('returns the list form as it is', () => {
    const where = [{ field: 'kind', op: '==', value: 'tool.invoke' }];
    expect(targetConditions({ where })).toEqual(where);
  });

  it('skips rows that are not conditions, as a hand-edited URL can hold', () => {
    const where = [
      null,
      'kind',
      { op: '==', value: 'x' },
      { field: 'kind', op: '==', value: { nested: true } },
      { field: 'kind', op: '==', value: 'tool.invoke' },
    ] as unknown as MetricTarget['where'];
    expect(targetConditions({ where })).toEqual([
      { field: 'kind', op: '==', value: 'tool.invoke' },
    ]);
    expect(
      targetConditions({ where: 'kind' as unknown as MetricTarget['where'] })
    ).toEqual([]);
  });

  it('reads the old dict form as == and in', () => {
    expect(
      targetConditions({ where: { channel: 'web', tier: ['gold', 'silver'] } })
    ).toEqual([
      { field: 'channel', op: '==', value: 'web' },
      { field: 'tier', op: 'in', value: ['gold', 'silver'] },
    ]);
  });

  it('reads an old key named like a special field as the attribute', () => {
    expect(
      targetConditions({ where: { status: 'ok' } }, [{ field: 'status' }])
    ).toEqual([{ field: 'attributes.status', op: '==', value: 'ok' }]);
  });

  it('is empty without conditions', () => {
    expect(targetConditions({})).toEqual([]);
    expect(targetConditions(null)).toEqual([]);
  });
});

describe('targetSpanKind', () => {
  it("is a preset's own span kind", () => {
    expect(targetSpanKind({ on: 'tool_call' }, CHOICES)).toBe('tool.invoke');
  });

  it("is a span target's kind condition, written either way", () => {
    expect(
      targetSpanKind(
        {
          on: 'span',
          where: [{ field: 'kind', op: '==', value: 'retrieval' }],
        },
        CHOICES
      )
    ).toBe('retrieval');
    expect(
      targetSpanKind(
        {
          on: 'span',
          where: [{ field: 'kind', op: '==', value: 'tool_call' }],
        },
        CHOICES
      )
    ).toBe('tool.invoke');
  });

  it('is null for a turn or a span target without a single kind', () => {
    expect(targetSpanKind({ on: 'turn' }, CHOICES)).toBeNull();
    expect(
      targetSpanKind(
        {
          on: 'span',
          where: [{ field: 'kind', op: 'in', value: ['a', 'b'] }],
        },
        CHOICES
      )
    ).toBeNull();
  });

  it('reads only kind conditions that pick a kind (== and a one-item in)', () => {
    const kindOf = (op: string, value: string | string[]) =>
      targetSpanKind(
        { on: 'span', where: [{ field: 'kind', op, value }] },
        CHOICES
      );
    expect(kindOf('!=', 'tool.invoke')).toBeNull();
    expect(kindOf('matches', 'tool.*')).toBeNull();
    expect(kindOf('in', ['retrieval'])).toBe('retrieval');
  });
});

describe('isTargetShape', () => {
  it.each([
    [{ on: 'turn' }, true],
    [{ on: 'span', where: [{ field: 'kind', op: '==', value: 'x' }] }, true],
    [{ on: 'turn', where: { channel: 'web', tier: ['a', 'b'] } }, true],
    [{ on: 'span', where: [null] }, false],
    [{ on: 'span', where: [{ op: '==', value: 'x' }] }, false],
    [{ on: 'span', where: 'kind' }, false],
    [{ on: 'span', where: { channel: { nested: 1 } } }, false],
    [{ on: 'tool_call', name: 3 }, false],
    [{ where: [] }, false],
    [[{ on: 'turn' }], false],
  ])('%j is a target shape: %s', (value, expected) => {
    expect(isTargetShape(value)).toBe(expected);
  });
});

describe('isTargetOnValue', () => {
  it('accepts target values and rejects junk', () => {
    expect(isTargetOnValue('tool_call')).toBe(true);
    expect(isTargetOnValue('Three-Turn')).toBe(false);
  });
});

describe('getMetricTargetIcon', () => {
  const kinds = [
    { on: 'turn' },
    { on: 'tool_call', span_kind: 'tool.invoke' },
    { on: 'retrieval', span_kind: 'retrieval' },
  ];
  const iconId = (
    on: string,
    choices?: typeof kinds,
    where?: { field: string; op: string; value: string }[]
  ) =>
    render(
      getMetricTargetIcon(on, choices, 'small', where)
    ).container.querySelector('svg')?.dataset.testid;

  it('gives a per-span target the icon of its span kind', () => {
    expect(iconId('tool_call', kinds)).toBe('BuildIcon');
    expect(iconId('retrieval', kinds)).toBe('SearchIcon');
  });

  it("gives custom spans their kind condition's icon, else a generic one", () => {
    expect(
      iconId('span', kinds, [{ field: 'kind', op: '==', value: 'tool.invoke' }])
    ).toBe('BuildIcon');
    expect(
      iconId('span', kinds, [{ field: 'app.tier', op: '==', value: 'gold' }])
    ).toBe('TuneOutlinedIcon');
  });

  it('keeps the turn and conversation icons', () => {
    expect(iconId('turn', kinds)).toBe('ChatBubbleOutlineIcon');
    expect(iconId('conversation', kinds)).toBe('ForumOutlinedIcon');
  });

  it('falls back to one icon for spans when the kinds are not loaded', () => {
    expect(iconId('tool_call')).toBe('AccountTreeOutlinedIcon');
  });
});
