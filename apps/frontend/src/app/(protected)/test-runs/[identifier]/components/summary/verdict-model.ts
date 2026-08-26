import type {
  VerdictRequirement,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';

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

export const CHAR_TO_STATE: Record<string, CellState> = {
  '.': 'pending',
  P: 'passed',
  F: 'failed',
  S: 'scored',
  E: 'error',
  X: 'na',
};

export interface GroupTestAggregate {
  total: number;
  passed: number;
  failed: number;
  rollup: CellState[];
}

export function aggregateMetric(row: VerdictRow): { passRate: number | null } {
  const resolved = row.passed + row.failed;
  if (resolved === 0) return { passRate: null };
  return { passRate: row.passed / resolved };
}

export interface VerdictBlock {
  tests: number;
  metrics: number;
}

// Per-requirement (tests x metrics) shape behind verdicts_planned -- the
// total isn't simply (all tests) x (all metrics) since different
// requirements can scope to different test subsets. Assumes every metric
// within one requirement applies to the same test subset (true today).
export function computeVerdictBlocks(
  requirements: VerdictRequirement[],
  rows: VerdictRow[]
): VerdictBlock[] {
  return requirements.map(req => {
    const reqRows = rows.filter(r => req.metric_keys.includes(r.metric_key));
    const tests = reqRows[0]
      ? reqRows[0].passed + reqRows[0].failed + reqRows[0].pending
      : 0;
    return { tests, metrics: req.metric_keys.length };
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
