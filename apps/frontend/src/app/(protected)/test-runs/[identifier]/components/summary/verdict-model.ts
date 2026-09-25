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
  /** Tests with at least one cell that applies -- excludes columns N/A for every row. */
  applicable: number;
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

export const REQUIREMENT_ROLLUP_HINT =
  'Per test: passed only if every metric on it passed, failed if any metric failed.';

export const BUILTIN_LABEL = '(Built-in)';
export const BUILTIN_HINT =
  'Scored on every multi-turn test, not set on any requirement. A failed goal fails the whole test.';

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
