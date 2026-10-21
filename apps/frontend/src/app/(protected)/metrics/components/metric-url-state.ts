import { TEST_TYPES } from '@/constants/test-types';
import type { FilterState } from './MetricsDirectoryTab';

/**
 * The metrics page keeps its quick and drawer filters in the URL, so going back
 * from a metric, a reload, or a shared link shows the same list. Search text
 * stays out: rewriting the URL on every keystroke would flood the history.
 */

const LIST_KEYS = {
  backend: 'backend',
  type: 'type',
  scoreType: 'score_type',
  metricScope: 'scope',
} as const satisfies Partial<Record<keyof FilterState, string>>;

const REQUIREMENT_PARAM = 'requirement';

const SCORE_TYPES = ['numeric', 'categorical'];
const METRIC_SCOPES: string[] = [TEST_TYPES.SINGLE_TURN, TEST_TYPES.MULTI_TURN];

/** Every URL key this module owns, so writing filters clears stale ones first. */
const FILTER_PARAMS = [...Object.values(LIST_KEYS), REQUIREMENT_PARAM];

const EMPTY_METRIC_FILTERS: FilterState = {
  search: '',
  backend: [],
  type: [],
  scoreType: [],
  metricScope: [],
  requirement: '',
};

/** Values that don't parse are dropped, so a hand-edited link can't break the page. */
export function filtersFromSearchParams(params: URLSearchParams): FilterState {
  const all = (key: string) => params.getAll(key).filter(Boolean);
  return {
    ...EMPTY_METRIC_FILTERS,
    backend: all(LIST_KEYS.backend),
    type: all(LIST_KEYS.type),
    scoreType: all(LIST_KEYS.scoreType).filter(v => SCORE_TYPES.includes(v)),
    metricScope: all(LIST_KEYS.metricScope).filter(v =>
      METRIC_SCOPES.includes(v)
    ),
    requirement: params.get(REQUIREMENT_PARAM) ?? '',
  };
}

/** *current* with the filters replaced. Other params (`assignMode`, ...) are kept. */
export function withMetricUrlState(
  current: URLSearchParams,
  filters: FilterState
): URLSearchParams {
  const next = new URLSearchParams(current);
  FILTER_PARAMS.forEach(key => next.delete(key));

  for (const [field, key] of Object.entries(LIST_KEYS) as [
    keyof typeof LIST_KEYS,
    string,
  ][]) {
    filters[field].forEach(value => next.append(key, value));
  }
  if (filters.requirement.trim()) {
    next.set(REQUIREMENT_PARAM, filters.requirement);
  }
  return next;
}

/** True when the URL narrows the list, so a prefetched unfiltered page won't match. */
export function hasMetricUrlFilters(params: URLSearchParams): boolean {
  // Parsed rather than key presence, so an empty or invalid value doesn't skip the prefetch.
  const filters = filtersFromSearchParams(params);
  return (
    (Object.keys(LIST_KEYS) as (keyof typeof LIST_KEYS)[]).some(
      field => filters[field].length > 0
    ) || filters.requirement.trim() !== ''
  );
}
