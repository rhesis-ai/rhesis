import React from 'react';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import ForumOutlinedIcon from '@mui/icons-material/ForumOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import { TEST_TYPES } from '@/constants/test-types';
import type {
  MetricConfig,
  MetricTarget,
  MetricTargetChoice,
  MetricTargetOn,
} from '@/utils/api-client/interfaces/metric';

/** Target `on` values the UI treats specially. The full list comes from `GET /metrics/targets`. */
export const METRIC_TARGET = {
  TURN: 'turn',
  CONVERSATION: 'conversation',
} as const satisfies Record<string, MetricTargetOn>;

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

/** The registry label for a target, with its name when it has one. */
export function formatMetricTarget(
  target: Pick<MetricTarget, 'on' | 'name'>,
  choices: Pick<MetricTargetChoice, 'on' | 'label'>[] | undefined
): string {
  const label = choices?.find(c => c.on === target.on)?.label ?? target.on;
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

/** The target to send: `name` only for a per-span target, and only when set. */
export function toMetricTarget(
  value: { on: string; name?: string },
  choices: MetricTargetChoice[]
): MetricTarget {
  const perSpan = choices.find(c => c.on === value.on)?.per_span ?? false;
  const name = value.name?.trim();
  return perSpan && name ? { on: value.on, name } : { on: value.on };
}

/**
 * The target to store after an edit. Settings the editor doesn't show
 * (`within`, `aggregate`, `min_share`) are kept while `on` stays the same.
 */
export function editedTarget(
  stored: MetricTarget | null,
  edited: { on: string; name?: string },
  choices: MetricTargetChoice[]
): MetricTarget {
  const next = toMetricTarget(edited, choices);
  if (!stored || stored.on !== next.on) return next;
  const { name: _name, ...rest } = stored;
  return { ...rest, ...next };
}

export function getMetricTargetIcon(on: string): React.ReactElement {
  switch (on) {
    case METRIC_TARGET.TURN:
      return <ChatBubbleOutlineIcon fontSize="small" />;
    case METRIC_TARGET.CONVERSATION:
      return <ForumOutlinedIcon fontSize="small" />;
    default:
      return <AccountTreeOutlinedIcon fontSize="small" />;
  }
}
