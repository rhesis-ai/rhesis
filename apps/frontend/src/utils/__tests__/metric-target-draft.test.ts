import type {
  ConditionOperatorChoice,
  MetricTarget,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';
import type { SpanAttributeCatalogue } from '@/utils/api-client/interfaces/telemetry';
import {
  conditionFromDraft,
  draftFromTarget,
  draftProblem,
  emptyCondition,
  fieldOptions,
  operatorLabel,
  SPECIAL_FIELDS_GROUP,
  targetFromDraft,
  targetKey,
  valueForOperator,
  valueSuggestions,
  readKeySuggestions,
} from '../metric-target-draft';

// As GET /metrics/targets sends them.
const OPERATORS: ConditionOperatorChoice[] = [
  { op: '==', takes_value: true, value_type: 'text' },
  { op: '!=', takes_value: true, value_type: 'text' },
  { op: '<', takes_value: true, value_type: 'number' },
  { op: 'in', takes_value: true, value_type: 'list' },
  { op: 'matches', takes_value: true, value_type: 'pattern' },
  { op: 'exists', takes_value: false, value_type: 'none' },
  { op: 'not_exists', takes_value: false, value_type: 'none' },
];
const SPECIAL_FIELDS = [
  { field: 'kind', label: 'Kind' },
  { field: 'name', label: 'Name' },
  { field: 'status', label: 'Status' },
];
const CHOICES: MetricTargetChoice[] = [
  { on: 'turn', label: 'Each turn', description: '', per_span: false },
  { on: 'run', label: 'The whole run', description: '', per_span: false },
  {
    on: 'tool_call',
    label: 'Each tool call',
    description: '',
    per_span: true,
    span_kind: 'tool.invoke',
  },
];

const CATALOGUE: SpanAttributeCatalogue = {
  sampled_spans: 500,
  since: '2026-11-20T00:00:00Z',
  kinds: {
    'tool.invoke': {
      spans: 400,
      attributes: [
        {
          key: 'ai.tool.name',
          coverage: 1,
          type: 'string',
          top_values: [
            { value: 'issue_refund', count: 120, truncated: false },
            { value: 'cancel_order', count: 40, truncated: false },
          ],
          distinct: 2,
          unique: false,
        },
        {
          key: 'ai.tool.call.id',
          coverage: 1,
          type: 'string',
          top_values: [{ value: 'call_1', count: 1, truncated: false }],
          distinct: 400,
          unique: true,
        },
        {
          key: 'app.note',
          coverage: 0.5,
          type: 'string',
          top_values: [
            {
              value: 'a very long note that was c…',
              count: 9,
              truncated: true,
            },
            { value: 'short', count: 3, truncated: false },
          ],
          distinct: 5,
          unique: false,
        },
      ],
    },
    'llm.invoke': {
      spans: 100,
      attributes: [
        {
          key: 'app.note',
          coverage: 0.2,
          type: 'string',
          top_values: [{ value: 'short', count: 5, truncated: false }],
          distinct: 1,
          unique: false,
        },
      ],
    },
  },
};

const STORED: MetricTarget = {
  on: 'tool_call',
  name: 'issue_refund',
  within: 'billing_agent',
  where: [
    { field: 'app.channel', op: '!=', value: 'internal' },
    { field: 'duration_ms', op: '<', value: 2000 },
    { field: 'app.tier', op: 'in', value: ['gold', 'silver'] },
  ],
  read: { input: 'ai.tool.arguments' },
  aggregate: 'share',
  min_share: 0.9,
};

describe('draftFromTarget and targetFromDraft', () => {
  it('round-trip a stored target', () => {
    const draft = draftFromTarget(STORED, 'turn', SPECIAL_FIELDS);
    expect(draft.minSharePercent).toBe('90');
    expect(draft.conditions.map(c => c.value)).toEqual([
      'internal',
      '2000',
      ['gold', 'silver'],
    ]);
    expect(targetFromDraft(draft, CHOICES, OPERATORS)).toEqual(STORED);
  });

  it('starts a new target on the default with nothing else', () => {
    const draft = draftFromTarget(null, 'turn');
    expect(targetFromDraft(draft, CHOICES, OPERATORS)).toEqual({ on: 'turn' });
  });

  it('reads an old dict where as conditions', () => {
    const draft = draftFromTarget(
      { on: 'turn', where: { channel: 'web' } },
      'turn'
    );
    expect(targetFromDraft(draft, CHOICES, OPERATORS)).toEqual({
      on: 'turn',
      where: [{ field: 'channel', op: '==', value: 'web' }],
    });
  });

  it('drops what a target with one unit cannot take', () => {
    const draft = {
      ...draftFromTarget(STORED, 'turn'),
      on: 'run',
    };
    expect(targetFromDraft(draft, CHOICES, OPERATORS)).toEqual({ on: 'run' });
  });

  it('keeps name off custom spans and within off a turn', () => {
    const base = draftFromTarget(STORED, 'turn');
    expect(
      targetFromDraft({ ...base, on: 'span' }, CHOICES, OPERATORS).name
    ).toBeUndefined();
    const turn = targetFromDraft({ ...base, on: 'turn' }, CHOICES, OPERATORS);
    expect(turn.name).toBeUndefined();
    expect(turn.within).toBeUndefined();
    expect(turn.where).toHaveLength(3);
  });

  it('sends min_share only with share', () => {
    const draft = {
      ...draftFromTarget(STORED, 'turn'),
      aggregate: 'any' as const,
    };
    const target = targetFromDraft(draft, CHOICES, OPERATORS);
    expect(target.aggregate).toBe('any');
    expect(target.min_share).toBeUndefined();
  });
});

describe('conditionFromDraft', () => {
  const row = (op: string, value: string | string[]) => ({
    ...emptyCondition(op),
    field: 'f',
    value,
  });

  it('sends no value for an operator that takes none', () => {
    expect(conditionFromDraft(row('exists', 'x'), OPERATORS)).toEqual({
      field: 'f',
      op: 'exists',
    });
  });

  it('is null until the row is complete', () => {
    expect(conditionFromDraft(row('==', ''), OPERATORS)).toBeNull();
    expect(conditionFromDraft(row('<', 'abc'), OPERATORS)).toBeNull();
    expect(conditionFromDraft(row('in', []), OPERATORS)).toBeNull();
    expect(conditionFromDraft(row('~', 'x'), OPERATORS)).toBeNull();
    expect(
      conditionFromDraft({ ...row('==', 'x'), field: ' ' }, OPERATORS)
    ).toBeNull();
  });

  it('sends a number for a numeric operator and a list for in', () => {
    expect(conditionFromDraft(row('<', '1.5'), OPERATORS)?.value).toBe(1.5);
    expect(
      conditionFromDraft(row('in', [' a ', 'b']), OPERATORS)?.value
    ).toEqual(['a', 'b']);
  });
});

describe('valueForOperator', () => {
  it('keeps the value across a change between one value and a list', () => {
    expect(valueForOperator('a', OPERATORS[3])).toEqual(['a']);
    expect(valueForOperator(['a', 'b'], OPERATORS[0])).toBe('a');
    expect(valueForOperator('a', OPERATORS[5])).toBe('');
  });
});

describe('draftProblem', () => {
  it('asks custom spans for a condition', () => {
    const draft = draftFromTarget({ on: 'span' }, 'turn');
    expect(draftProblem(draft, CHOICES, OPERATORS)).toMatch(
      /at least one condition/
    );
  });

  it('flags incomplete rows', () => {
    const draft = {
      ...draftFromTarget(null, 'turn'),
      conditions: [emptyCondition('==')],
    };
    expect(draftProblem(draft, CHOICES, OPERATORS)).toMatch(/incomplete/);
  });

  it('checks the share is a percentage', () => {
    const draft = {
      ...draftFromTarget(null, 'tool_call'),
      aggregate: 'share' as const,
      minSharePercent: '150',
    };
    expect(draftProblem(draft, CHOICES, OPERATORS)).toMatch(/percentage/);
    expect(
      draftProblem({ ...draft, minSharePercent: '90' }, CHOICES, OPERATORS)
    ).toBeNull();
  });
});

describe('targetKey', () => {
  it('is the same for the dict and list forms of one target', () => {
    expect(targetKey({ on: 'turn', where: { a: 'b' } })).toBe(
      targetKey({ on: 'turn', where: [{ field: 'a', op: '==', value: 'b' }] })
    );
    expect(targetKey({ on: 'turn' })).not.toBe(targetKey({ on: 'run' }));
  });
});

describe('fieldOptions', () => {
  const options = fieldOptions(SPECIAL_FIELDS, CATALOGUE, CHOICES);

  it('lists the special fields first, with the API labels', () => {
    expect(options.slice(0, 3).map(o => [o.field, o.label, o.group])).toEqual([
      ['kind', 'Kind', SPECIAL_FIELDS_GROUP],
      ['name', 'Name', SPECIAL_FIELDS_GROUP],
      ['status', 'Status', SPECIAL_FIELDS_GROUP],
    ]);
  });

  it("groups attribute keys by kind under the preset's label, most common kind first", () => {
    const groups = [...new Set(options.slice(3).map(o => o.group))];
    expect(groups).toEqual(['Each tool call (tool.invoke)', 'llm.invoke']);
  });

  it('leaves out unique keys and shows coverage with untruncated values', () => {
    expect(options.map(o => o.field)).not.toContain('ai.tool.call.id');
    const note = options.find(o => o.key === 'tool.invoke:app.note');
    expect(note?.hint).toBe('on 50%: short');
  });
});

describe('valueSuggestions', () => {
  it('suggests the top values across kinds, most common first', () => {
    expect(valueSuggestions('ai.tool.name', CATALOGUE)).toEqual([
      'issue_refund',
      'cancel_order',
    ]);
  });

  it('never suggests a value the catalogue cut short', () => {
    expect(valueSuggestions('app.note', CATALOGUE)).toEqual(['short']);
  });

  it('suggests nothing for a unique key', () => {
    expect(valueSuggestions('ai.tool.call.id', CATALOGUE)).toEqual([]);
  });

  it("suggests the catalogue's kinds for the kind field", () => {
    expect(valueSuggestions('kind', CATALOGUE)).toEqual([
      'tool.invoke',
      'llm.invoke',
    ]);
  });
});

describe('readKeySuggestions', () => {
  it("offers the kind's own keys, unique ones included", () => {
    expect(readKeySuggestions(CATALOGUE, 'tool.invoke')).toEqual([
      'ai.tool.call.id',
      'ai.tool.name',
      'app.note',
    ]);
  });
});

describe('operatorLabel', () => {
  it('words known operators and shows an unknown one as itself', () => {
    expect(operatorLabel('not_in')).toBe('is none of');
    expect(operatorLabel('~=')).toBe('~=');
  });
});
