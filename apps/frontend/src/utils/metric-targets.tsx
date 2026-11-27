import React from 'react';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import ForumOutlinedIcon from '@mui/icons-material/ForumOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import { getSpanTypeInfo } from '@/constants/span-types';
import { TEST_TYPES } from '@/constants/test-types';
import type {
  MetricConfig,
  MetricTarget,
  MetricTargetChoice,
  MetricTargetCondition,
  MetricTargetOn,
  SpecialFieldChoice,
} from '@/utils/api-client/interfaces/metric';

/**
 * Target `on` values the UI treats specially. The presets come from
 * `GET /metrics/targets`; `span` is not one of them (the presets are short forms
 * of it), so the builder offers it on its own as "Custom spans".
 */
export const METRIC_TARGET = {
  TURN: 'turn',
  CONVERSATION: 'conversation',
  SPAN: 'span',
} as const satisfies Record<string, MetricTargetOn>;

/** The SDK's name for `on: "span"`, which the registry doesn't list. */
export const SPAN_TARGET_CHOICE: MetricTargetChoice = {
  on: METRIC_TARGET.SPAN,
  label: 'Custom spans',
  description:
    'Every span that meets the conditions below: its input and output as its kind reads them, unless you choose what to read.',
  per_span: true,
};

/**
 * Special fields the UI reads itself. Which special fields exist, and their
 * labels, come from `GET /metrics/targets`; these mirror the SDK's names.
 */
export const SPECIAL_FIELD = {
  KIND: 'kind',
} as const;

/** Reads an attribute whose key is also a special field's name: `attributes.status`. */
const ATTRIBUTE_PREFIX = 'attributes.';

/** Shape of a target `on` value, used to drop junk from hand-edited URLs. */
const TARGET_ON_PATTERN = /^[a-z_]+$/;

export function isTargetOnValue(value: string): boolean {
  return TARGET_ON_PATTERN.test(value);
}

export function getMetricTarget(metric: {
  config?: MetricConfig | null;
}): MetricTarget | null {
  return metric.config?.target ?? null;
}

/**
 * A target's conditions as a list. Rows stored before conditions existed hold
 * attribute values by key (a list meaning any of them): read as `==` and `in`,
 * as the API reads them.
 */
export function targetConditions(
  target: Pick<MetricTarget, 'where'> | null | undefined,
  specialFields: Pick<SpecialFieldChoice, 'field'>[] = []
): MetricTargetCondition[] {
  const where = target?.where;
  if (!where) return [];
  if (Array.isArray(where)) return where;
  const special = new Set(specialFields.map(f => f.field));
  return Object.entries(where).map(([key, value]) => ({
    field: special.has(key) ? `${ATTRIBUTE_PREFIX}${key}` : key,
    op: Array.isArray(value) ? 'in' : '==',
    value,
  }));
}

/** The registry label for a target, with its name when it has one. */
export function formatMetricTarget(
  target: Pick<MetricTarget, 'on' | 'name'>,
  choices: Pick<MetricTargetChoice, 'on' | 'label'>[] | undefined
): string {
  const label =
    choices?.find(c => c.on === target.on)?.label ??
    (target.on === METRIC_TARGET.SPAN ? SPAN_TARGET_CHOICE.label : target.on);
  return target.name ? `${label} (${target.name})` : label;
}

/**
 * Whether a metric runs on tests of this type. A conversation metric never
 * runs on single-turn tests, and a metric that needs a reference answer never
 * runs on multi-turn tests, which have none. Unknown types show everything.
 */
export function metricRunsOnTestType(
  metric: {
    config?: MetricConfig | null;
    ground_truth_required?: boolean | null;
  },
  testType: string | null | undefined
): boolean {
  const type = testType?.toLowerCase();
  if (type === TEST_TYPES.MULTI_TURN.toLowerCase()) {
    return !metric.ground_truth_required;
  }
  if (type !== TEST_TYPES.SINGLE_TURN.toLowerCase()) {
    return true;
  }
  return getMetricTarget(metric)?.on !== METRIC_TARGET.CONVERSATION;
}

/**
 * The targets an editor offers, in registry order. `supported` narrows to a
 * metric's `supported_targets` (null means unknown, so everything). A metric
 * that needs a reference answer can't judge single spans or a conversation.
 */
export function offeredTargets(
  choices: MetricTargetChoice[],
  {
    supported,
    groundTruthRequired = false,
  }: { supported?: string[] | null; groundTruthRequired?: boolean } = {}
): MetricTargetChoice[] {
  return choices.filter(
    c =>
      (!supported || supported.includes(c.on)) &&
      !(
        groundTruthRequired &&
        (c.per_span || c.on === METRIC_TARGET.CONVERSATION)
      )
  );
}

/**
 * The presets an editor offers plus "Custom spans" when the metric can judge
 * single spans: it can whenever it can take a per-span preset.
 */
export function offeredTargetsWithCustom(
  choices: MetricTargetChoice[],
  options: { supported?: string[] | null; groundTruthRequired?: boolean } = {}
): MetricTargetChoice[] {
  const offered = offeredTargets(choices, options);
  const custom = options.supported
    ? options.supported.includes(METRIC_TARGET.SPAN)
    : offered.some(c => c.per_span);
  return custom ? [...offered, SPAN_TARGET_CHOICE] : offered;
}

type TargetChoiceKind = Pick<MetricTargetChoice, 'on' | 'span_kind'>;

/**
 * The span kind a target judges: a preset's own, or the kind a span target's
 * condition names (`kind == tool.invoke`). Null for anything else.
 */
export function targetSpanKind(
  target: Pick<MetricTarget, 'on' | 'where'>,
  choices?: TargetChoiceKind[]
): string | null {
  const preset = choices?.find(c => c.on === target.on)?.span_kind;
  if (preset) return preset;
  if (target.on !== METRIC_TARGET.SPAN) return null;
  const kind = targetConditions(target).find(
    c => c.field === SPECIAL_FIELD.KIND && typeof c.value === 'string'
  );
  if (!kind || typeof kind.value !== 'string') return null;
  // A kind may be written as a preset's name (`tool_call`) or its span kind.
  return choices?.find(c => c.on === kind.value)?.span_kind ?? kind.value;
}

/**
 * A target's icon. A per-span target takes the icon the trace view gives its
 * span kind, so "each tool call" looks like a tool span; that needs `choices`.
 * A span target takes its kind condition's icon, else a generic one.
 */
export function getMetricTargetIcon(
  on: string,
  choices?: TargetChoiceKind[],
  fontSize: 'small' | 'inherit' = 'small',
  where?: MetricTarget['where']
): React.ReactElement {
  const spanKind = targetSpanKind({ on, where }, choices);
  if (spanKind) {
    const Icon = getSpanTypeInfo(spanKind).icon;
    return <Icon fontSize={fontSize} />;
  }
  switch (on) {
    case METRIC_TARGET.TURN:
      return <ChatBubbleOutlineIcon fontSize={fontSize} />;
    case METRIC_TARGET.CONVERSATION:
      return <ForumOutlinedIcon fontSize={fontSize} />;
    case METRIC_TARGET.SPAN:
      return <TuneOutlinedIcon fontSize={fontSize} />;
    default:
      return <AccountTreeOutlinedIcon fontSize={fontSize} />;
  }
}
