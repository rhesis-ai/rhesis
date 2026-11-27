import type {
  MetricTarget,
  MetricTargetChoice,
} from '@/utils/api-client/interfaces/metric';
import { METRIC_TARGET } from '@/utils/metric-targets';
import {
  EMPTY_TRACE_DRAWER_FILTERS,
  type TraceDrawerFilters,
  type TraceView,
} from './trace-filter-params';
import { withTraceUrlState } from './trace-url-state';

/** URL key naming the metric a target filter came from, so the page can say so. */
export const FROM_METRIC_PARAM = 'from_metric';

type TargetChoiceKind = Pick<MetricTargetChoice, 'on' | 'span_kind'>;

/** The list filters that hold the values a target was narrowed to. */
type ListFilterField =
  | 'spanTypes'
  | 'spanNames'
  | 'models'
  | 'tools'
  | 'agents';

/** Which filter holds a per-span target's name, by span kind; others match the span name. */
const NAME_FILTER_BY_SPAN_KIND: Record<string, ListFilterField> = {
  'tool.invoke': 'tools',
  'llm.invoke': 'models',
  'agent.invoke': 'agents',
};

export interface TargetTraceFilters {
  view: TraceView;
  filters: Partial<TraceDrawerFilters>;
}

/**
 * The Traces page filters that show what a target judges. A per-span target opens
 * the spans view on its span kind and name; a turn opens the root spans; the
 * conversation opens multi-turn traces; the whole run opens every trace.
 */
export function targetTraceFilters(
  target: Pick<MetricTarget, 'on' | 'name'>,
  choices: TargetChoiceKind[] | undefined
): TargetTraceFilters {
  const spanKind = choices?.find(c => c.on === target.on)?.span_kind;
  if (spanKind) {
    const filters: Partial<TraceDrawerFilters> = { spanTypes: [spanKind] };
    if (target.name) {
      filters[NAME_FILTER_BY_SPAN_KIND[spanKind] ?? 'spanNames'] = [
        target.name,
      ];
    }
    return { view: 'spans', filters };
  }
  if (target.on === METRIC_TARGET.TURN) {
    return { view: 'spans', filters: { isRoot: true } };
  }
  if (target.on === METRIC_TARGET.CONVERSATION) {
    return { view: 'traces', filters: { traceType: 'Multi-Turn' } };
  }
  return { view: 'traces', filters: {} };
}

/**
 * What a target narrows to that the Traces filters can't apply: the agent its
 * spans run inside, and attributes their root span must have. Read as phrases
 * ("inside billing_agent", "channel is web"), empty when everything applies.
 */
export function unappliedRefinements(
  target: Pick<MetricTarget, 'within' | 'where'>
): string[] {
  const phrases: string[] = [];
  if (target.within) phrases.push(`inside ${target.within}`);
  for (const [key, value] of Object.entries(target.where ?? {})) {
    phrases.push(
      Array.isArray(value)
        ? `${key} is one of ${value.map(String).join(', ')}`
        : `${key} is ${String(value)}`
    );
  }
  return phrases;
}

/** A link to the Traces page filtered to what a metric's target judges. */
export function tracesHrefForTarget(
  target: Pick<MetricTarget, 'on' | 'name'>,
  choices: TargetChoiceKind[] | undefined,
  metricId?: string
): string {
  const { view, filters } = targetTraceFilters(target, choices);
  const params = withTraceUrlState(new URLSearchParams(), view, {
    ...EMPTY_TRACE_DRAWER_FILTERS,
    ...filters,
  });
  if (metricId) params.set(FROM_METRIC_PARAM, metricId);
  const query = params.toString();
  return query ? `/traces?${query}` : '/traces';
}

/** *current* without the filters a target set; filters the user added stay. */
export function withoutTargetFilters(
  current: TraceDrawerFilters,
  applied: Partial<TraceDrawerFilters>
): TraceDrawerFilters {
  const next: TraceDrawerFilters = { ...current };
  for (const key of Object.keys(applied) as (keyof TraceDrawerFilters)[]) {
    const value = applied[key];
    const existing = next[key];
    if (Array.isArray(value) && Array.isArray(existing)) {
      const remaining = existing.filter(v => !value.includes(v));
      (next as unknown as Record<string, unknown>)[key] = remaining.length
        ? remaining
        : undefined;
    } else if (existing === value) {
      delete next[key];
    }
  }
  return Object.fromEntries(
    Object.entries(next).filter(([, value]) => value !== undefined)
  ) as TraceDrawerFilters;
}
