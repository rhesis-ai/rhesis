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

export function countActiveInsightsFilters(input: {
  endpointId: string;
  behaviorIds: string[];
}): number {
  let count = input.endpointId ? 1 : 0;
  if (isBehaviorFilterActive(input.behaviorIds)) {
    count += 1;
  }
  return count;
}

export function hasActiveInsightsFilters(input: {
  endpointId: string;
  behaviorIds: string[];
}): boolean {
  return countActiveInsightsFilters(input) > 0;
}
