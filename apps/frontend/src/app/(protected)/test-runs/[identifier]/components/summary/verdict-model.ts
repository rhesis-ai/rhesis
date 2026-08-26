import type {
  VerdictRequirement,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';

export type CellState =
  | 'pending'
  | 'passed'
  | 'failed'
  | 'scored'
  | 'error'
  | 'na'
  | 'inFlight';

const CHAR_TO_STATE: Record<string, CellState> = {
  '.': 'pending',
  P: 'passed',
  F: 'failed',
  S: 'scored',
  E: 'error',
  X: 'na',
};

export function cellState(
  char: string,
  isGenerating: boolean,
  isEvaluating: boolean
): CellState {
  const base = CHAR_TO_STATE[char] ?? 'pending';
  if (base === 'pending' && (isGenerating || isEvaluating)) return 'inFlight';
  return base;
}

// Most-severe-wins order for reducing several metric verdicts (for the same
// test) into one roll-up cell. A test reads as failed if any metric on it
// failed or errored, even while other metrics are still pending.
export const SEVERITY_ORDER: CellState[] = [
  'failed',
  'error',
  'inFlight',
  'pending',
  'scored',
  'na',
  'passed',
];

export function reduceCellStates(states: CellState[]): CellState {
  if (states.length === 0) return 'pending';
  const present = new Set(states);
  for (const candidate of SEVERITY_ORDER) {
    if (present.has(candidate)) return candidate;
  }
  return states[0];
}

// One CellState per test, reduced across a requirement group's metric rows
// via reduceCellStates -- this is the per-test roll-up shown in the group
// header strip, not a per-metric strip.
export function computeGroupRollup(
  groupRows: VerdictRow[],
  testIds: string[],
  generatingIds: Set<string>,
  evaluatingIds: Set<string>
): CellState[] {
  const rollup: CellState[] = [];
  for (let i = 0; i < testIds.length; i++) {
    const tid = testIds[i];
    const isGenerating = generatingIds.has(tid);
    const isEvaluating = evaluatingIds.has(tid);
    const statesForTest = groupRows.map(row =>
      cellState(row.verdicts[i] ?? '.', isGenerating, isEvaluating)
    );
    rollup.push(reduceCellStates(statesForTest));
  }
  return rollup;
}

export interface GroupTestAggregate {
  total: number;
  passed: number;
  failed: number;
  rollup: CellState[];
}

// Total/passed/failed and the roll-up strip are derived from the exact same
// per-test array so the numeric badges and the strip's red cells can never
// disagree. A test counts as failed if its roll-up state is 'failed' or
// 'error'; 'passed' only counts tests fully resolved with no failure --
// pending/in-flight tests count toward neither, mirroring how
// aggregateMetric excludes pending from a metric's own pass rate.
//
// Generic over the row scope: pass a single requirement's rows for a group
// roll-up, or the whole matrix's rows for a run-wide roll-up (e.g. the Pass
// Rate KPI card's sparkline).
export function aggregateGroupByTest(
  groupRows: VerdictRow[],
  testIds: string[],
  generatingIds: Set<string>,
  evaluatingIds: Set<string>
): GroupTestAggregate {
  const rollup = computeGroupRollup(
    groupRows,
    testIds,
    generatingIds,
    evaluatingIds
  );
  let passed = 0;
  let failed = 0;
  for (const state of rollup) {
    if (state === 'passed') passed++;
    else if (state === 'failed' || state === 'error') failed++;
  }
  return { total: rollup.length, passed, failed, rollup };
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
