import { TestRun } from '@/utils/api-client/interfaces/test-run';
import { DEFAULT_INSIGHTS_TIME_RANGE, InsightsFilters } from '../types';

export interface InsightsBehaviorOption {
  id: string;
  name: string;
  count: number;
}

/**
 * Test runs: an optional narrowing *within* the time range (see
 * `InsightsTimeRangeFilterSection`) -- empty selection always falls back to
 * "every run in the window", both when unset and when explicitly unchecked
 * down to zero. There's no distinct "explicitly zero runs" state here.
 */
export function checkedIdsFromFilter(
  allIds: string[],
  selectedIds: string[]
): string[] {
  if (selectedIds.length === 0) {
    return allIds;
  }
  const allowed = new Set(selectedIds);
  return allIds.filter(id => allowed.has(id));
}

export function idsFromCheckedSelection(
  allIds: string[],
  checkedIds: string[]
): string[] {
  if (checkedIds.length === 0 || checkedIds.length === allIds.length) {
    return [];
  }
  return checkedIds;
}

/**
 * Behaviors/statuses: a "hide/exclude" toggle over `allIds`, where
 * unchecking everything is a real, meaningful state (show nothing) --
 * distinct from having never touched the filter (show everything). `null`
 * carries that "unset" meaning so it isn't confused with the explicit `[]`.
 */
export function checkedIdsFromOptionalFilter(
  allIds: string[],
  selectedIds: string[] | null
): string[] {
  if (selectedIds === null) {
    return allIds;
  }
  const allowed = new Set(selectedIds);
  return allIds.filter(id => allowed.has(id));
}

/** Checking everything collapses to "no filter" (null); any other count is kept as-is, including zero. */
export function idsFromCheckedSelectionOptional(
  allIds: string[],
  checkedIds: string[]
): string[] | null {
  if (checkedIds.length === allIds.length) {
    return null;
  }
  return checkedIds;
}

export function isOptionalFilterActive(ids: string[] | null): boolean {
  return ids !== null;
}

export function isRunFilterActive(
  filters: Pick<InsightsFilters, 'timeRange' | 'testRunIds'>
): boolean {
  return (
    filters.timeRange !== DEFAULT_INSIGHTS_TIME_RANGE ||
    filters.testRunIds.length > 0
  );
}

export interface InsightsTestRunOption {
  id: string;
  label: string;
}

export function formatInsightsTestRunLabel(
  run: Pick<TestRun, 'id' | 'name' | 'created_at'>
): string {
  const name = run.name?.trim() || 'Untitled run';
  if (!run.created_at) {
    return name;
  }
  const date = new Date(run.created_at).toLocaleString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
  return `${name} · ${date}`;
}
