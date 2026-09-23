import type {
  VerdictRequirement,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';
import { passRate } from '@/constants/outcomes';

// 'generating' and 'evaluating' are deliberately distinct: the first covers a
// whole test column (no metric can be scored until the model has answered),
// the second is per-cell. Rendering them identically would hide that
// generation is the slow phase and evaluation the fast tail.
export type CellState =
  | 'pending'
  | 'passed'
  | 'failed'
  | 'scored'
  | 'error'
  | 'na'
  | 'generating'
  | 'evaluating';

const NOT_APPLICABLE = 'X';
export const ERROR_CHAR = 'E';

export const CHAR_TO_STATE: Record<string, CellState> = {
  '.': 'pending',
  P: 'passed',
  F: 'failed',
  S: 'scored',
  [ERROR_CHAR]: 'error',
  [NOT_APPLICABLE]: 'na',
};

export interface GroupTestAggregate {
  total: number;
  passed: number;
  failed: number;
  rollup: CellState[];
}

/** A metric's pass rate as a percentage (0-100), or null if nothing resolved. */
export function aggregateMetric(row: VerdictRow): { passRate: number | null } {
  return { passRate: passRate(row.passed, row.failed) };
}

// Match on the requirement too: two requirements can carry a metric with the
// same key, and each has its own row scoped to its own tests.
export function rowsForRequirement(
  requirement: VerdictRequirement,
  rows: VerdictRow[]
): VerdictRow[] {
  return rows.filter(
    r =>
      r.requirement_id === requirement.id &&
      requirement.metric_keys.includes(r.metric_key)
  );
}

export const NO_METRICS_LABEL = 'No metrics configured';

/**
 * A stand-in row for a requirement with no metrics, built from its tests' own
 * outcomes -- without it those tests have no cell anywhere in the grid, and a
 * test that errored for lack of metrics counts as a failure nobody can see.
 * Null when the requirement has metric rows of its own, or no tests.
 */
export function metriclessRow(
  requirement: VerdictRequirement
): VerdictRow | null {
  const status = requirement.test_status ?? '';
  if (requirement.metric_keys.length > 0 || !/[^X]/.test(status)) return null;
  const count = (chars: string) =>
    [...status].filter(c => chars.includes(c)).length;
  return {
    requirement_id: requirement.id,
    metric_key: '',
    metric_name: NO_METRICS_LABEL,
    metric_id: null,
    ambiguous: false,
    verdicts: status,
    overrides: '0'.repeat(status.length),
    passed: count('P'),
    failed: count('FE'),
    pending: count('.'),
  };
}

/** Every row the grid shows, placeholders for metric-less requirements included. */
export function withMetriclessRows(
  requirements: VerdictRequirement[],
  rows: VerdictRow[]
): VerdictRow[] {
  const placeholders = requirements
    .map(metriclessRow)
    .filter((row): row is VerdictRow => row !== null);
  return placeholders.length > 0 ? [...rows, ...placeholders] : rows;
}

export interface VerdictBlock {
  tests: number;
  metrics: number;
}

// Per-requirement (tests x metrics) shape behind verdicts_planned -- the
// total isn't simply (all tests) x (all metrics) since different
// requirements can scope to different test subsets. Only rows and columns
// with at least one applicable cell count: a metric scoped out of every test
// (a multi-turn metric on single-turn tests) adds no verdicts. Assumes the
// applicable metrics within one requirement share one test subset (true today).
export function computeVerdictBlocks(
  requirements: VerdictRequirement[],
  rows: VerdictRow[]
): VerdictBlock[] {
  return requirements.map(req => {
    const applicable = rowsForRequirement(req, rows).filter(r =>
      /[^X]/.test(r.verdicts)
    );
    const columns = new Set<number>();
    for (const row of applicable) {
      [...row.verdicts].forEach((c, i) => {
        if (c !== NOT_APPLICABLE) columns.add(i);
      });
    }
    return { tests: columns.size, metrics: applicable.length };
  });
}

export function formatVerdictBlocks(blocks: VerdictBlock[]): string {
  const parts = blocks
    .filter(b => b.tests > 0 && b.metrics > 0)
    .map(b => `${b.tests}×${b.metrics}`);
  if (parts.length === 0) return '';
  if (parts.length === 1) return `blocks: ${parts[0]}`;
  return `blocks: ${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}
