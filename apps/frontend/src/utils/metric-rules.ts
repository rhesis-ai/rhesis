import type {
  MetricConfig,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';
import { offeredTargets } from '@/utils/metric-targets';

/** The SDK classes a rule metric is built from. */
export const RULE_CLASSES = {
  FIELD: 'FieldRule',
  RESPONSE: 'ResponseRule',
  TOOL_CALLS: 'ToolCallTrajectory',
} as const;

export type RuleClass = (typeof RULE_CLASSES)[keyof typeof RULE_CLASSES];

/** The rules the create form offers. Tool Call Trajectory is a seeded metric. */
export const CREATABLE_RULE_CLASSES: { value: RuleClass; label: string }[] = [
  { value: RULE_CLASSES.FIELD, label: 'Field rule' },
  { value: RULE_CLASSES.RESPONSE, label: 'Response rule' },
];

export function isRuleClass(
  value: string | null | undefined
): value is RuleClass {
  return Object.values(RULE_CLASSES).some(c => c === value);
}

type FieldKind = 'number' | 'text';

export const ATTRIBUTE_FIELD = 'attributes';
export const SPAN_COUNT_FIELD = 'span_count';

export const RULE_FIELDS: { value: string; label: string; kind: FieldKind }[] =
  [
    { value: 'duration_ms', label: 'Duration (ms)', kind: 'number' },
    { value: 'status', label: 'Status', kind: 'text' },
    { value: 'error_count', label: 'Failed spans', kind: 'number' },
    { value: SPAN_COUNT_FIELD, label: 'Number of spans', kind: 'number' },
    { value: 'tokens.input', label: 'Input tokens', kind: 'number' },
    { value: 'tokens.output', label: 'Output tokens', kind: 'number' },
    { value: 'tokens.total', label: 'Total tokens', kind: 'number' },
    { value: 'cost_usd', label: 'Cost (USD)', kind: 'number' },
    { value: 'input', label: 'Input', kind: 'text' },
    { value: 'output', label: 'Output', kind: 'text' },
    { value: 'length.input', label: 'Input length', kind: 'number' },
    { value: 'length.output', label: 'Output length', kind: 'number' },
    { value: ATTRIBUTE_FIELD, label: 'Attribute', kind: 'text' },
  ];

export const RULE_OPERATORS = {
  LT: '<',
  LTE: '<=',
  GT: '>',
  GTE: '>=',
  EQ: '==',
  NE: '!=',
  IN: 'in',
  NOT_IN: 'not_in',
  CONTAINS: 'contains',
  MATCHES: 'matches',
  EXISTS: 'exists',
  IS_JSON: 'is_json',
} as const;

export type RuleOperator = (typeof RULE_OPERATORS)[keyof typeof RULE_OPERATORS];

const OPERATOR_LABELS: Record<RuleOperator, string> = {
  [RULE_OPERATORS.LT]: '<',
  [RULE_OPERATORS.LTE]: '<=',
  [RULE_OPERATORS.GT]: '>',
  [RULE_OPERATORS.GTE]: '>=',
  [RULE_OPERATORS.EQ]: '==',
  [RULE_OPERATORS.NE]: '!=',
  [RULE_OPERATORS.IN]: 'is one of',
  [RULE_OPERATORS.NOT_IN]: 'is not one of',
  [RULE_OPERATORS.CONTAINS]: 'contains',
  [RULE_OPERATORS.MATCHES]: 'matches the pattern',
  [RULE_OPERATORS.EXISTS]: 'exists',
  [RULE_OPERATORS.IS_JSON]: 'is valid JSON',
};

const COMPARISONS: RuleOperator[] = [
  RULE_OPERATORS.LT,
  RULE_OPERATORS.LTE,
  RULE_OPERATORS.GT,
  RULE_OPERATORS.GTE,
];
const EQUALITY: RuleOperator[] = [
  RULE_OPERATORS.EQ,
  RULE_OPERATORS.NE,
  RULE_OPERATORS.IN,
  RULE_OPERATORS.NOT_IN,
];
const TEXT_ONLY: RuleOperator[] = [
  RULE_OPERATORS.CONTAINS,
  RULE_OPERATORS.MATCHES,
  RULE_OPERATORS.IS_JSON,
];
const LIST_OPERATORS: RuleOperator[] = [
  RULE_OPERATORS.IN,
  RULE_OPERATORS.NOT_IN,
];
const VALUELESS: RuleOperator[] = [
  RULE_OPERATORS.EXISTS,
  RULE_OPERATORS.IS_JSON,
];

function fieldKind(field: string): FieldKind {
  return RULE_FIELDS.find(f => f.value === field)?.kind ?? 'text';
}

/** The operators that make sense for a field: comparisons for numbers, text checks for text. */
export function operatorsFor(
  field: string
): { value: RuleOperator; label: string }[] {
  const ops =
    field === ATTRIBUTE_FIELD
      ? [...COMPARISONS, ...EQUALITY, ...TEXT_ONLY, RULE_OPERATORS.EXISTS]
      : fieldKind(field) === 'number'
        ? [...COMPARISONS, ...EQUALITY]
        : [...EQUALITY, ...TEXT_ONLY];
  return ops.map(value => ({ value, label: OPERATOR_LABELS[value] }));
}

export function operatorTakesValue(op: string): boolean {
  return !VALUELESS.some(o => o === op);
}

export function operatorTakesList(op: string): boolean {
  return LIST_OPERATORS.some(o => o === op);
}

export const RESPONSE_MATCHES = {
  EXACT: 'exact',
  CONTAINS: 'contains',
  MATCHES: 'matches',
  SIMILAR: 'similar',
} as const;

export const RESPONSE_MATCH_LABELS: Record<string, string> = {
  [RESPONSE_MATCHES.EXACT]: 'Matches the expected response exactly',
  [RESPONSE_MATCHES.CONTAINS]: 'Contains the expected response',
  [RESPONSE_MATCHES.MATCHES]: 'Matches the expected response as a pattern',
  [RESPONSE_MATCHES.SIMILAR]: 'Is similar to the expected response',
};

export const SIMILARITY_LABELS: Record<string, string> = {
  rouge_l: 'ROUGE-L',
  edit_distance: 'Edit distance',
};

export const TRAJECTORY_MATCH_LABELS: Record<string, string> = {
  exact: 'Exact: same calls, same order, nothing else',
  in_order: 'In order: expected calls in order, others allowed',
  any_order: 'Any order: same calls, any order',
  subset: 'Subset: every call made was expected',
  superset: 'Superset: every expected call was made',
};

export const ARGUMENT_MATCH_LABELS: Record<string, string> = {
  exact: 'Exact',
  partial: 'Partial: only the listed keys',
  ignore: 'Ignore',
};

/** A rule as the editor holds it: raw text, parsed once into the stored config. */
export interface RuleDraft {
  ruleClass: RuleClass;
  field: string;
  attributeKey: string;
  op: string;
  value: string;
  negate: boolean;
  spanKind: string;
  spanName: string;
  match: string;
  similarity: string;
  minSimilarity: string;
  trajectoryMatch: string;
  arguments: string;
}

export const initialRuleDraft: RuleDraft = {
  ruleClass: RULE_CLASSES.FIELD,
  field: 'duration_ms',
  attributeKey: '',
  op: RULE_OPERATORS.LTE,
  value: '5000',
  negate: false,
  spanKind: '',
  spanName: '',
  match: RESPONSE_MATCHES.EXACT,
  similarity: 'rouge_l',
  minSimilarity: '0.8',
  trajectoryMatch: 'in_order',
  arguments: 'partial',
};

function storedField(draft: RuleDraft): string {
  return draft.field === ATTRIBUTE_FIELD
    ? `${ATTRIBUTE_FIELD}.${draft.attributeKey.trim()}`
    : draft.field;
}

function parseScalar(text: string, numeric: boolean): string | number {
  const trimmed = text.trim();
  const asNumber = Number(trimmed);
  return trimmed !== '' && !Number.isNaN(asNumber) && numeric
    ? asNumber
    : trimmed;
}

function parsedValue(draft: RuleDraft): unknown {
  // An attribute holds whatever the endpoint sent, so a number-looking value is a number.
  const numeric =
    fieldKind(draft.field) === 'number' || draft.field === ATTRIBUTE_FIELD;
  if (operatorTakesList(draft.op)) {
    return draft.value
      .split(',')
      .map(v => v.trim())
      .filter(Boolean)
      .map(v => parseScalar(v, numeric));
  }
  return parseScalar(draft.value, numeric);
}

/** The settings a rule stores in `config`, without its target. */
export function ruleConfig(draft: RuleDraft): Record<string, unknown> {
  if (draft.ruleClass === RULE_CLASSES.RESPONSE) {
    return draft.match === RESPONSE_MATCHES.SIMILAR
      ? {
          match: draft.match,
          similarity: draft.similarity,
          min_similarity: Number(draft.minSimilarity),
        }
      : { match: draft.match };
  }
  if (draft.ruleClass === RULE_CLASSES.TOOL_CALLS) {
    return { match: draft.trajectoryMatch, arguments: draft.arguments };
  }
  const config: Record<string, unknown> = {
    field: storedField(draft),
    op: draft.op,
  };
  if (operatorTakesValue(draft.op)) config.value = parsedValue(draft);
  if (draft.negate) config.negate = true;
  if (draft.field === SPAN_COUNT_FIELD) {
    if (draft.spanKind) config.span_kind = draft.spanKind;
    if (draft.spanName.trim()) config.span_name = draft.spanName.trim();
  }
  return config;
}

function asText(value: unknown): string {
  if (Array.isArray(value)) return value.map(asText).join(', ');
  if (value === null || value === undefined) return '';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** The editor's draft for a stored rule. */
export function ruleDraftFromConfig(
  className: string | null | undefined,
  config: MetricConfig | null | undefined
): RuleDraft {
  const c = config ?? {};
  const ruleClass = isRuleClass(className) ? className : RULE_CLASSES.FIELD;
  const field = typeof c.field === 'string' ? c.field : '';
  const isAttribute = field.startsWith(`${ATTRIBUTE_FIELD}.`);
  return {
    ...initialRuleDraft,
    ruleClass,
    field: isAttribute ? ATTRIBUTE_FIELD : field || initialRuleDraft.field,
    attributeKey: isAttribute ? field.slice(ATTRIBUTE_FIELD.length + 1) : '',
    op: typeof c.op === 'string' ? c.op : initialRuleDraft.op,
    value: 'value' in c ? asText(c.value) : '',
    negate: c.negate === true,
    spanKind: typeof c.span_kind === 'string' ? c.span_kind : '',
    spanName: typeof c.span_name === 'string' ? c.span_name : '',
    match:
      ruleClass === RULE_CLASSES.RESPONSE && typeof c.match === 'string'
        ? c.match
        : initialRuleDraft.match,
    similarity:
      typeof c.similarity === 'string'
        ? c.similarity
        : initialRuleDraft.similarity,
    minSimilarity:
      typeof c.min_similarity === 'number'
        ? String(c.min_similarity)
        : initialRuleDraft.minSimilarity,
    trajectoryMatch:
      ruleClass === RULE_CLASSES.TOOL_CALLS && typeof c.match === 'string'
        ? c.match
        : initialRuleDraft.trajectoryMatch,
    arguments:
      typeof c.arguments === 'string'
        ? c.arguments
        : initialRuleDraft.arguments,
  };
}

/** One line saying what a rule checks, e.g. "duration_ms <= 5000". */
export function describeRule(draft: RuleDraft): string {
  if (draft.ruleClass === RULE_CLASSES.RESPONSE) {
    const base = `output ${RESPONSE_MATCH_LABELS[draft.match]?.toLowerCase() ?? draft.match}`;
    return draft.match === RESPONSE_MATCHES.SIMILAR
      ? `${base} (${SIMILARITY_LABELS[draft.similarity] ?? draft.similarity} >= ${draft.minSimilarity})`
      : base;
  }
  if (draft.ruleClass === RULE_CLASSES.TOOL_CALLS) {
    return `tool calls match the expected ones (${draft.trajectoryMatch.replace('_', ' ')}, arguments ${draft.arguments})`;
  }
  let subject = storedField(draft);
  if (draft.field === SPAN_COUNT_FIELD) {
    const scope = [draft.spanKind, draft.spanName.trim()]
      .filter(Boolean)
      .join(' named ');
    if (scope) subject = `span_count(${scope})`;
  }
  const op = OPERATOR_LABELS[draft.op as RuleOperator] ?? draft.op;
  const statement = operatorTakesValue(draft.op)
    ? `${subject} ${op} ${asText(parsedValue(draft))}`
    : `${subject} ${op}`;
  return draft.negate ? `not (${statement})` : statement;
}

/** What is wrong with a draft, or null when it can be saved. */
export function ruleDraftError(draft: RuleDraft): string | null {
  if (draft.ruleClass === RULE_CLASSES.RESPONSE) {
    if (draft.match !== RESPONSE_MATCHES.SIMILAR) return null;
    const min = Number(draft.minSimilarity);
    return draft.minSimilarity.trim() === '' ||
      Number.isNaN(min) ||
      min < 0 ||
      min > 1
      ? 'Minimum similarity must be a number from 0 to 1'
      : null;
  }
  if (draft.ruleClass === RULE_CLASSES.TOOL_CALLS) return null;
  if (!draft.field) return 'Pick a field';
  if (draft.field === ATTRIBUTE_FIELD && !draft.attributeKey.trim()) {
    return 'Enter the attribute key';
  }
  if (!operatorsFor(draft.field).some(o => o.value === draft.op)) {
    return 'Pick an operator';
  }
  if (!operatorTakesValue(draft.op)) return null;
  if (operatorTakesList(draft.op)) {
    const values = parsedValue(draft);
    return Array.isArray(values) && values.length > 0
      ? null
      : 'Enter at least one value';
  }
  if (!draft.value.trim()) return 'Enter a value';
  if (
    COMPARISONS.some(o => o === draft.op) &&
    Number.isNaN(Number(draft.value.trim()))
  ) {
    return 'Enter a number';
  }
  if (draft.op === RULE_OPERATORS.MATCHES) {
    try {
      new RegExp(draft.value);
    } catch {
      return 'Enter a valid regular expression';
    }
  }
  return null;
}

/**
 * The targets a rule can take. A field rule reads any unit; a response rule
 * compares with the expected response, which a single span or a conversation
 * doesn't have; Tool Call Trajectory compares a whole list of calls.
 */
export function ruleTargetChoices(
  ruleClass: RuleClass,
  choices: MetricTargetChoice[]
): MetricTargetChoice[] {
  if (ruleClass === RULE_CLASSES.RESPONSE) {
    return offeredTargets(choices, { groundTruthRequired: true });
  }
  if (ruleClass === RULE_CLASSES.TOOL_CALLS) {
    return choices.filter(c => !c.per_span);
  }
  return choices;
}
