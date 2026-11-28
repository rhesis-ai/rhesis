import type { MetricTarget } from '@/utils/api-client/interfaces/metric';
import {
  EMPTY_TRACE_DRAWER_FILTERS,
  type TraceDrawerFilters,
} from './trace-filter-params';
import { withTraceUrlState } from './trace-url-state';

/** URL key naming the metric a target filter came from, so the page can say so. */
export const FROM_METRIC_PARAM = 'from_metric';

/**
 * A link to the Traces page showing exactly the spans a metric's target picks:
 * the spans view with the target itself as the filter, matched by the API as
 * evaluation matches it (each matching span, each turn's root, each trace's
 * first root for the run or the conversation).
 */
export function tracesHrefForTarget(
  target: MetricTarget,
  metricId?: string
): string {
  const params = withTraceUrlState(new URLSearchParams(), 'spans', {
    ...EMPTY_TRACE_DRAWER_FILTERS,
    target: JSON.stringify(target),
  });
  if (metricId) params.set(FROM_METRIC_PARAM, metricId);
  return `/traces?${params.toString()}`;
}

/** *current* without the target filter; filters the user added stay. */
export function withoutTargetFilter(
  current: TraceDrawerFilters
): TraceDrawerFilters {
  const { target: _target, ...rest } = current;
  return rest;
}
