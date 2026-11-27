import type {
  ConditionOperatorChoice,
  ConditionValueType,
  MetricTarget,
  MetricTargetAggregate,
  MetricTargetAttributeValue,
  MetricTargetChoice,
  MetricTargetCondition,
  SpecialFieldChoice,
} from '@/utils/api-client/interfaces/metric';
import type {
  SpanAttributeCatalogue,
  SpanAttributeSummary,
} from '@/utils/api-client/interfaces/telemetry';
import {
  METRIC_TARGET,
  SPECIAL_FIELD,
  targetConditions,
} from '@/utils/metric-targets';

/**
 * The target builder's working copy. Text fields hold what was typed, so a
 * half-written condition survives until it is complete; `targetFromDraft`
 * turns it into the target the API stores.
 */

/** What an operator compares with, mirroring the SDK's `ValueType`. */
export const VALUE_TYPE = {
  NONE: 'none',
  NUMBER: 'number',
  LIST: 'list',
  TEXT: 'text',
  PATTERN: 'pattern',
} as const satisfies Record<string, ConditionValueType>;

/** How several units' verdicts make the metric's: the SDK's `Aggregation`. */
export const TARGET_AGGREGATE = {
  ALL: 'all',
  ANY: 'any',
  SHARE: 'share',
} as const satisfies Record<string, MetricTargetAggregate>;

/** Default share of units that must pass, in percent, when "at least" is picked. */
export const DEFAULT_MIN_SHARE_PERCENT = '90';

/** Words for the operators the API sends; an unknown one shows as itself. */
const OPERATOR_LABELS: Record<string, string> = {
  '==': 'is',
  '!=': 'is not',
  '<': 'is under',
  '<=': 'is at most',
  '>': 'is over',
  '>=': 'is at least',
  in: 'is any of',
  not_in: 'is none of',
  contains: 'contains',
  matches: 'matches pattern',
  exists: 'is set',
  not_exists: 'is not set',
};

export function operatorLabel(op: string): string {
  return OPERATOR_LABELS[op] ?? op;
}

export interface ConditionDraft {
  /** Stable React key; never sent. */
  id: string;
  field: string;
  op: string;
  /** Text for one value, a list for `in`/`not_in`. */
  value: string | string[];
}

export interface TargetDraft {
  on: string;
  /** Per-span presets only. */
  name: string;
  /** Per-span presets and custom spans. */
  within: string;
  conditions: ConditionDraft[];
  readInput: string;
  readOutput: string;
  aggregate: MetricTargetAggregate;
  /** Percent, as typed; only read with aggregate `share`. */
  minSharePercent: string;
}

let nextConditionId = 0;
function conditionId(): string {
  nextConditionId += 1;
  return `condition-${nextConditionId}`;
}

export function emptyCondition(op = ''): ConditionDraft {
  return { id: conditionId(), field: '', op, value: '' };
}

function valueText(value: MetricTargetAttributeValue): string {
  return String(value);
}

function conditionDraft(condition: MetricTargetCondition): ConditionDraft {
  const { value } = condition;
  return {
    id: conditionId(),
    field: condition.field,
    op: condition.op,
    value: Array.isArray(value)
      ? value.map(valueText)
      : value === undefined || value === null
        ? ''
        : valueText(value),
  };
}

/** The draft for a stored target, or for a new one judging `defaultOn`. */
export function draftFromTarget(
  target: MetricTarget | null | undefined,
  defaultOn: string,
  specialFields: SpecialFieldChoice[] = []
): TargetDraft {
  const share = target?.min_share;
  return {
    on: target?.on ?? defaultOn,
    name: target?.name ?? '',
    within: target?.within ?? '',
    conditions: targetConditions(target, specialFields).map(conditionDraft),
    readInput: target?.read?.input ?? '',
    readOutput: target?.read?.output ?? '',
    aggregate: target?.aggregate ?? TARGET_AGGREGATE.ALL,
    minSharePercent:
      share === undefined
        ? DEFAULT_MIN_SHARE_PERCENT
        : String(Math.round(share * 1000) / 10),
  };
}

type ChoiceShape = Pick<MetricTargetChoice, 'on' | 'per_span'>;

/** Judges spans one by one: a per-span preset, or custom spans. */
export function isPerSpanTarget(on: string, choices: ChoiceShape[]): boolean {
  return (
    on === METRIC_TARGET.SPAN ||
    (choices.find(c => c.on === on)?.per_span ?? false)
  );
}

/**
 * Has several units, so it takes conditions, `read` and a pass rule: per-span
 * targets and each turn. The conversation and the whole run are one unit.
 */
export function isPerUnitTarget(on: string, choices: ChoiceShape[]): boolean {
  return on === METRIC_TARGET.TURN || isPerSpanTarget(on, choices);
}

export function findOperator(
  op: string,
  operators: ConditionOperatorChoice[]
): ConditionOperatorChoice | undefined {
  return operators.find(o => o.op === op);
}

/** A number typed as text, or null when it isn't one. */
function parsedNumber(text: string): number | null {
  if (!text.trim()) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

/** The condition as the API takes it, or null while it is incomplete. */
export function conditionFromDraft(
  draft: ConditionDraft,
  operators: ConditionOperatorChoice[]
): MetricTargetCondition | null {
  const field = draft.field.trim();
  const operator = findOperator(draft.op, operators);
  if (!field || !operator) return null;
  if (!operator.takes_value) return { field, op: operator.op };
  if (operator.value_type === VALUE_TYPE.LIST) {
    const values = (Array.isArray(draft.value) ? draft.value : [draft.value])
      .map(v => v.trim())
      .filter(Boolean);
    return values.length ? { field, op: operator.op, value: values } : null;
  }
  const text = Array.isArray(draft.value)
    ? (draft.value[0] ?? '')
    : draft.value;
  if (operator.value_type === VALUE_TYPE.NUMBER) {
    const value = parsedNumber(text);
    return value === null ? null : { field, op: operator.op, value };
  }
  return text.trim() ? { field, op: operator.op, value: text } : null;
}

/** A value kept across an operator change: a list becomes its first entry and back. */
export function valueForOperator(
  value: string | string[],
  operator: ConditionOperatorChoice | undefined
): string | string[] {
  if (!operator || !operator.takes_value) return '';
  if (operator.value_type === VALUE_TYPE.LIST) {
    if (Array.isArray(value)) return value;
    return value.trim() ? [value] : [];
  }
  return Array.isArray(value) ? (value[0] ?? '') : value;
}

/**
 * The target to store. Each part goes only where the SDK accepts it: `name` on a
 * preset, `within` on per-span targets, conditions, `read` and the pass rule on
 * targets with several units. Incomplete condition rows are left out.
 */
export function targetFromDraft(
  draft: TargetDraft,
  choices: ChoiceShape[],
  operators: ConditionOperatorChoice[]
): MetricTarget {
  const target: MetricTarget = { on: draft.on };
  const perSpan = isPerSpanTarget(draft.on, choices);
  if (!isPerUnitTarget(draft.on, choices)) return target;

  const name = draft.name.trim();
  if (perSpan && draft.on !== METRIC_TARGET.SPAN && name) target.name = name;
  const within = draft.within.trim();
  if (perSpan && within) target.within = within;

  const where = draft.conditions
    .map(c => conditionFromDraft(c, operators))
    .filter((c): c is MetricTargetCondition => c !== null);
  if (where.length) target.where = where;

  const input = draft.readInput.trim();
  const output = draft.readOutput.trim();
  if (input || output) {
    target.read = {
      ...(input ? { input } : {}),
      ...(output ? { output } : {}),
    };
  }

  if (draft.aggregate !== TARGET_AGGREGATE.ALL) {
    target.aggregate = draft.aggregate;
  }
  if (draft.aggregate === TARGET_AGGREGATE.SHARE) {
    const percent = parsedNumber(draft.minSharePercent);
    if (percent !== null) target.min_share = percent / 100;
  }
  return target;
}

/**
 * What stops the draft from being saved, in words, or null. The API checks the
 * rest (operators, value types, patterns) and names the problem itself.
 */
export function draftProblem(
  draft: TargetDraft,
  choices: ChoiceShape[],
  operators: ConditionOperatorChoice[]
): string | null {
  if (!draft.on) return 'Choose what the metric judges.';
  const complete = draft.conditions.filter(
    c => conditionFromDraft(c, operators) !== null
  ).length;
  if (complete < draft.conditions.length) {
    return 'Finish or remove the incomplete conditions.';
  }
  if (draft.on === METRIC_TARGET.SPAN && complete === 0) {
    return 'Custom spans need at least one condition. To judge the whole trace, choose the whole run.';
  }
  if (
    isPerUnitTarget(draft.on, choices) &&
    draft.aggregate === TARGET_AGGREGATE.SHARE
  ) {
    const percent = parsedNumber(draft.minSharePercent);
    if (percent === null || percent <= 0 || percent > 100) {
      return 'The share that must pass is a percentage above 0, up to 100.';
    }
  }
  return null;
}

/** A target with its parts in one order, so two that mean the same compare equal. */
export function targetKey(target: MetricTarget | null | undefined): string {
  if (!target) return '';
  return JSON.stringify({
    on: target.on,
    name: target.name ?? null,
    within: target.within ?? null,
    where: targetConditions(target).map(c => [c.field, c.op, c.value ?? null]),
    read: [target.read?.input ?? null, target.read?.output ?? null],
    aggregate: target.aggregate ?? TARGET_AGGREGATE.ALL,
    min_share: target.min_share ?? null,
  });
}

/* ------------------------------------------------------------------------ */
/* Suggestions from the attribute catalogue                                  */
/* ------------------------------------------------------------------------ */

/** One field a condition can read, as the field picker lists it. */
export interface FieldOption {
  field: string;
  label: string;
  /** The group heading: special fields, or a span kind. */
  group: string;
  /** "on 92% · gold, silver, free"; empty for special fields. */
  hint: string;
  /** Unique within the list: a key can show under several kinds. */
  key: string;
}

/** Heading for the special fields in the field picker. */
export const SPECIAL_FIELDS_GROUP = 'Any span';

const HINT_VALUES = 3;

function percent(coverage: number): string {
  return `${Math.round(coverage * 100)}%`;
}

function attributeHint(attribute: SpanAttributeSummary): string {
  const values = attribute.top_values
    .filter(v => !v.truncated)
    .slice(0, HINT_VALUES)
    .map(v => v.value);
  const coverage = `on ${percent(attribute.coverage)}`;
  return values.length ? `${coverage}: ${values.join(', ')}` : coverage;
}

/** The heading for a span kind: the preset that judges it, else the kind. */
export function kindLabel(
  kind: string,
  choices: Pick<MetricTargetChoice, 'span_kind' | 'label'>[]
): string {
  const preset = choices.find(c => c.span_kind === kind)?.label;
  return preset ? `${preset} (${kind})` : kind;
}

/**
 * The fields a condition can read: the special fields first, then each kind's
 * attribute keys from the catalogue, most common first. Keys where nearly every
 * span has its own value (ids) are left out; they can still be typed.
 */
export function fieldOptions(
  specialFields: SpecialFieldChoice[],
  catalogue: SpanAttributeCatalogue | undefined,
  choices: Pick<MetricTargetChoice, 'span_kind' | 'label'>[]
): FieldOption[] {
  const special: FieldOption[] = specialFields.map(f => ({
    field: f.field,
    label: f.label,
    group: SPECIAL_FIELDS_GROUP,
    hint: '',
    key: `special:${f.field}`,
  }));
  const kinds = Object.entries(catalogue?.kinds ?? {}).sort(
    ([, a], [, b]) => b.spans - a.spans
  );
  const attributes = kinds.flatMap(([kind, { attributes: keys }]) =>
    keys
      .filter(a => !a.unique)
      .slice()
      .sort((a, b) => b.coverage - a.coverage)
      .map(a => ({
        field: a.key,
        label: a.key,
        group: kindLabel(kind, choices),
        hint: attributeHint(a),
        key: `${kind}:${a.key}`,
      }))
  );
  return [...special, ...attributes];
}

/** The label a special field shows, or the field itself for an attribute key. */
export function fieldLabel(
  field: string,
  specialFields: SpecialFieldChoice[]
): string {
  return specialFields.find(f => f.field === field)?.label ?? field;
}

/**
 * Values to suggest for a condition on `field`: the kinds the catalogue holds
 * for the kind field, else the field's top values across kinds, most common
 * first. A value the catalogue cut short would never match exactly, and a key
 * whose every span has its own value suggests nothing useful, so neither shows.
 */
export function valueSuggestions(
  field: string,
  catalogue: SpanAttributeCatalogue | undefined
): string[] {
  if (!catalogue || !field) return [];
  if (field === SPECIAL_FIELD.KIND) return Object.keys(catalogue.kinds);
  const counts = new Map<string, number>();
  for (const { attributes } of Object.values(catalogue.kinds)) {
    const attribute = attributes.find(a => a.key === field);
    if (!attribute || attribute.unique) continue;
    for (const v of attribute.top_values) {
      if (v.truncated) continue;
      counts.set(v.value, (counts.get(v.value) ?? 0) + v.count);
    }
  }
  return [...counts.entries()]
    .sort(([, a], [, b]) => b - a)
    .map(([value]) => value);
}

/**
 * Attribute keys to offer for `read`: the ones the target's span kind carries,
 * else every kind's. Unique keys stay: arguments and results differ per span.
 */
export function readKeySuggestions(
  catalogue: SpanAttributeCatalogue | undefined,
  spanKind: string | null
): string[] {
  if (!catalogue) return [];
  const kinds = spanKind
    ? [catalogue.kinds[spanKind]].filter(Boolean)
    : Object.values(catalogue.kinds);
  const keys = new Set<string>();
  kinds.forEach(k => k.attributes.forEach(a => keys.add(a.key)));
  return [...keys].sort();
}
