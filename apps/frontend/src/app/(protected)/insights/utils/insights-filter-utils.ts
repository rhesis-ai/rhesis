import { TestRun } from '@/utils/api-client/interfaces/test-run';
import {
  DEFAULT_INSIGHTS_TIME_RANGE,
  InsightsFilters,
  InsightsRunFilterMode,
} from '../types';

export interface InsightsBehaviorOption {
  id: string;
  name: string;
  count: number;
}

/** Empty selection means all behaviors are visible. */
export function isBehaviorFilterActive(behaviorIds: string[]): boolean {
  return behaviorIds.length > 0;
}

export function filterColumnsByBehaviorIds<T extends { id: string }>(
  columns: T[],
  behaviorIds: string[]
): T[] {
  if (behaviorIds.length === 0) {
    return columns;
  }
  const allowed = new Set(behaviorIds);
  return columns.filter(column => allowed.has(column.id));
}

export function checkedBehaviorIdsFromFilter(
  allIds: string[],
  behaviorIds: string[]
): string[] {
  if (behaviorIds.length === 0) {
    return allIds;
  }
  const allowed = new Set(behaviorIds);
  return allIds.filter(id => allowed.has(id));
}

export function behaviorIdsFromCheckedSelection(
  allIds: string[],
  checkedIds: string[]
): string[] {
  if (checkedIds.length === 0 || checkedIds.length === allIds.length) {
    return [];
  }
  return checkedIds;
}

export function isRunFilterActive(
  filters: Pick<InsightsFilters, 'runFilterMode' | 'timeRange' | 'testRunIds'>
): boolean {
  if (filters.runFilterMode === 'timeRange') {
    return filters.timeRange !== DEFAULT_INSIGHTS_TIME_RANGE;
  }
  return filters.testRunIds.length > 0;
}

export function countActiveInsightsFilters(input: {
  endpointId: string;
  behaviorIds: string[];
  runFilterMode: InsightsRunFilterMode;
  timeRange: InsightsFilters['timeRange'];
  testRunIds: string[];
}): number {
  let count = input.endpointId ? 1 : 0;
  if (isBehaviorFilterActive(input.behaviorIds)) {
    count += 1;
  }
  if (isRunFilterActive(input)) {
    count += 1;
  }
  return count;
}

export function hasActiveInsightsFilters(input: {
  endpointId: string;
  behaviorIds: string[];
  runFilterMode: InsightsRunFilterMode;
  timeRange: InsightsFilters['timeRange'];
  testRunIds: string[];
}): boolean {
  return countActiveInsightsFilters(input) > 0;
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

export function checkedTestRunIdsFromFilter(
  allIds: string[],
  filters: Pick<InsightsFilters, 'runFilterMode' | 'testRunIds'>
): string[] {
  if (filters.runFilterMode !== 'testRuns') {
    return [];
  }
  if (filters.testRunIds.length === 0) {
    return allIds;
  }
  const allowed = new Set(filters.testRunIds);
  return allIds.filter(id => allowed.has(id));
}

export function testRunIdsFromCheckedSelection(
  allIds: string[],
  checkedIds: string[]
): string[] {
  if (checkedIds.length === 0 || checkedIds.length === allIds.length) {
    return [];
  }
  return checkedIds;
}
