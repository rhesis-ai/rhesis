import {
  RULE_CLASSES,
  describeRule,
  initialRuleDraft,
  operatorsFor,
  ruleConfig,
  ruleDraftError,
  ruleDraftFromConfig,
  ruleTargetChoices,
  type RuleDraft,
} from '@/utils/metric-rules';
import type { MetricTargetChoice } from '@/utils/api-client/interfaces/metric';

const draft = (changes: Partial<RuleDraft>): RuleDraft => ({
  ...initialRuleDraft,
  ...changes,
});

const choices: MetricTargetChoice[] = [
  { on: 'turn', label: 'Each turn', description: '', per_span: false },
  {
    on: 'conversation',
    label: 'The conversation',
    description: '',
    per_span: false,
  },
  { on: 'run', label: 'The whole run', description: '', per_span: false },
  { on: 'tool_call', label: 'Each tool call', description: '', per_span: true },
];

describe('ruleConfig', () => {
  it('stores a number for a number field', () => {
    expect(ruleConfig(initialRuleDraft)).toEqual({
      field: 'duration_ms',
      op: '<=',
      value: 5000,
    });
  });

  it('stores an attribute under its key, and a list for in', () => {
    expect(
      ruleConfig(
        draft({
          field: 'attributes',
          attributeKey: 'rhesis.reported.metadata.channel',
          op: 'in',
          value: 'email, chat',
        })
      )
    ).toEqual({
      field: 'attributes.rhesis.reported.metadata.channel',
      op: 'in',
      value: ['email', 'chat'],
    });
  });

  it('stores a number-looking attribute value as a number for comparisons', () => {
    expect(
      ruleConfig(
        draft({
          field: 'attributes',
          attributeKey: 'tier',
          op: '>=',
          value: '2',
        })
      ).value
    ).toBe(2);
    expect(
      ruleConfig(
        draft({
          field: 'attributes',
          attributeKey: 'tier',
          op: 'in',
          value: '1, 2',
        })
      ).value
    ).toEqual([1, 2]);
  });

  it('keeps a value as text for contains and matches', () => {
    expect(
      ruleConfig(
        draft({
          field: 'attributes',
          attributeKey: 'version',
          op: 'contains',
          value: '2.0',
        })
      ).value
    ).toBe('2.0');
    expect(
      ruleConfig(
        draft({
          field: 'attributes',
          attributeKey: 'order',
          op: 'matches',
          value: '123',
        })
      ).value
    ).toBe('123');
  });

  it('leaves the value out where the operator takes none, and keeps negate', () => {
    expect(
      ruleConfig(draft({ field: 'output', op: 'is_json', negate: true }))
    ).toEqual({ field: 'output', op: 'is_json', negate: true });
  });

  it('limits a span count to a kind and a name', () => {
    expect(
      ruleConfig(
        draft({
          field: 'span_count',
          op: '==',
          value: '0',
          spanKind: 'tool_call',
          spanName: ' delete_account ',
        })
      )
    ).toEqual({
      field: 'span_count',
      op: '==',
      value: 0,
      span_kind: 'tool_call',
      span_name: 'delete_account',
    });
  });

  it('stores a response rule, with similarity only when similar', () => {
    expect(
      ruleConfig(draft({ ruleClass: RULE_CLASSES.RESPONSE, match: 'exact' }))
    ).toEqual({ match: 'exact' });
    expect(
      ruleConfig(
        draft({
          ruleClass: RULE_CLASSES.RESPONSE,
          match: 'similar',
          similarity: 'edit_distance',
          minSimilarity: '0.8',
        })
      )
    ).toEqual({
      match: 'similar',
      similarity: 'edit_distance',
      min_similarity: 0.8,
    });
  });
});

describe('ruleDraftFromConfig', () => {
  it('reads back what ruleConfig stores', () => {
    const original = draft({
      field: 'attributes',
      attributeKey: 'endpoint.response.status',
      op: 'in',
      value: '200, 201',
      negate: true,
    });
    const restored = ruleDraftFromConfig(
      RULE_CLASSES.FIELD,
      ruleConfig(original)
    );
    expect(ruleConfig(restored)).toEqual(ruleConfig(original));
  });

  it("reads Tool Call Trajectory's settings", () => {
    const restored = ruleDraftFromConfig(RULE_CLASSES.TOOL_CALLS, {
      match: 'exact',
      arguments: 'ignore',
      target: { on: 'run' },
    });
    expect(ruleConfig(restored)).toEqual({
      match: 'exact',
      arguments: 'ignore',
    });
  });
});

describe('describeRule', () => {
  it('says what a field rule checks', () => {
    expect(describeRule(initialRuleDraft)).toBe('duration_ms <= 5000');
    expect(
      describeRule(
        draft({
          field: 'output',
          op: 'matches',
          value: '[0-9]{3}-[0-9]{4}',
          negate: true,
        })
      )
    ).toBe('not (output matches the pattern [0-9]{3}-[0-9]{4})');
    expect(
      describeRule(
        draft({
          field: 'span_count',
          op: '==',
          value: '0',
          spanKind: 'tool_call',
          spanName: 'delete_account',
        })
      )
    ).toBe('span_count(tool_call named delete_account) == 0');
  });
});

describe('ruleDraftError', () => {
  it('accepts the default rule', () => {
    expect(ruleDraftError(initialRuleDraft)).toBeNull();
  });

  it.each([
    [{ value: 'fast' }, 'Enter a number'],
    [{ value: '' }, 'Enter a value'],
    [
      { field: 'attributes', op: '==', attributeKey: '' },
      'Enter the attribute key',
    ],
    [
      { field: 'output', op: 'matches', value: '(' },
      'Enter a valid regular expression',
    ],
    [{ field: 'status', op: 'in', value: ' , ' }, 'Enter at least one value'],
    [
      {
        ruleClass: RULE_CLASSES.RESPONSE,
        match: 'similar',
        minSimilarity: '2',
      },
      'Minimum similarity must be a number from 0 to 1',
    ],
  ])('refuses %j', (changes, message) => {
    expect(ruleDraftError(draft(changes as Partial<RuleDraft>))).toBe(message);
  });
});

describe('operatorsFor', () => {
  it('offers comparisons for numbers and text checks for text', () => {
    const numberOps = operatorsFor('duration_ms').map(o => o.value);
    const textOps = operatorsFor('output').map(o => o.value);
    expect(numberOps).toContain('<=');
    expect(numberOps).not.toContain('matches');
    expect(textOps).toContain('is_json');
    expect(textOps).not.toContain('<');
  });
});

describe('ruleTargetChoices', () => {
  const ons = (list: MetricTargetChoice[]) => list.map(c => c.on);

  it('lets a field rule take every target', () => {
    expect(ons(ruleTargetChoices(RULE_CLASSES.FIELD, choices))).toEqual([
      'turn',
      'conversation',
      'run',
      'tool_call',
    ]);
  });

  it('keeps a response rule off spans and conversations', () => {
    expect(ons(ruleTargetChoices(RULE_CLASSES.RESPONSE, choices))).toEqual([
      'turn',
      'run',
    ]);
  });
});
