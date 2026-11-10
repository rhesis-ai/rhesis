import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';

export type RequirementsView = 'cards' | 'table';

const VIEW_STORAGE_KEY = 'requirements:view';

/** The view this browser last picked; cards when unknown or unreadable. */
export function readRequirementsView(): RequirementsView {
  try {
    return window.localStorage.getItem(VIEW_STORAGE_KEY) === 'table'
      ? 'table'
      : 'cards';
  } catch {
    return 'cards';
  }
}

export function storeRequirementsView(view: RequirementsView): void {
  try {
    window.localStorage.setItem(VIEW_STORAGE_KEY, view);
  } catch {
    // Private mode or blocked storage: the choice just isn't remembered.
  }
}

export interface HierarchyRow {
  requirement: RequirementWithMetrics;
  /** How many parents above it are also on this page. */
  depth: number;
}

/**
 * Puts each child right after its parent when both are on the page, keeping
 * the page's own order otherwise. MUI X tree data is a Pro feature, so the
 * grouping is done here.
 */
export function orderByHierarchy(
  rows: RequirementWithMetrics[]
): HierarchyRow[] {
  const onPage = new Set(rows.map(r => String(r.id)));
  const childrenOf = new Map<string, RequirementWithMetrics[]>();
  for (const row of rows) {
    const parentId = row.parent_id ?? row.parent?.id;
    if (parentId && onPage.has(String(parentId)) && parentId !== row.id) {
      const list = childrenOf.get(String(parentId)) ?? [];
      list.push(row);
      childrenOf.set(String(parentId), list);
    }
  }
  const nestedIds = new Set(
    Array.from(childrenOf.values()).flatMap(list => list.map(r => String(r.id)))
  );

  const ordered: HierarchyRow[] = [];
  const seen = new Set<string>();
  const emit = (row: RequirementWithMetrics, depth: number) => {
    // Guards against a parent cycle in bad data.
    if (seen.has(String(row.id))) return;
    seen.add(String(row.id));
    ordered.push({ requirement: row, depth });
    for (const child of childrenOf.get(String(row.id)) ?? []) {
      emit(child, depth + 1);
    }
  };
  for (const row of rows) {
    if (!nestedIds.has(String(row.id))) emit(row, 0);
  }
  // Rows only reachable through a cycle still get shown.
  for (const row of rows) emit(row, 0);
  return ordered;
}

export interface CompletenessDot {
  key: 'description' | 'source' | 'examples' | 'metric';
  label: string;
  done: boolean;
}

/** Four checks a well-defined requirement passes. */
export function completeness(
  requirement: Pick<
    RequirementWithMetrics,
    'description' | 'sources' | 'examples_count' | 'metrics'
  >
): CompletenessDot[] {
  return [
    {
      key: 'description',
      label: 'Description',
      done: !!requirement.description?.trim(),
    },
    {
      key: 'source',
      label: 'Source',
      done: (requirement.sources ?? []).length > 0,
    },
    {
      key: 'examples',
      label: 'Examples',
      done: (requirement.examples_count ?? 0) > 0,
    },
    {
      key: 'metric',
      label: 'Metric',
      done: (requirement.metrics ?? []).length > 0,
    },
  ];
}
