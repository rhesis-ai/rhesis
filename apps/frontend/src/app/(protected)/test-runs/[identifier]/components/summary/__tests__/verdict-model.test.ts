import {
  cellState,
  reduceCellStates,
  computeGroupRollup,
  aggregateGroupByTest,
  aggregateMetric,
} from '../verdict-model';
import type { VerdictRow } from '@/utils/api-client/interfaces/test-run';

describe('cellState', () => {
  it.each([
    ['.', 'pending'],
    ['P', 'passed'],
    ['F', 'failed'],
    ['S', 'scored'],
    ['E', 'error'],
    ['X', 'na'],
  ] as const)('maps %s to %s', (char, expected) => {
    expect(cellState(char, false, false)).toBe(expected);
  });

  it('overrides pending to inFlight when generating', () => {
    expect(cellState('.', true, false)).toBe('inFlight');
  });

  it('overrides pending to inFlight when evaluating', () => {
    expect(cellState('.', false, true)).toBe('inFlight');
  });

  it('does not override passed even when generating', () => {
    expect(cellState('P', true, false)).toBe('passed');
  });

  it('does not override failed even when evaluating', () => {
    expect(cellState('F', false, true)).toBe('failed');
  });

  it('maps unknown char to pending', () => {
    expect(cellState('?', false, false)).toBe('pending');
  });
});

describe('reduceCellStates', () => {
  it('returns pending for empty input', () => {
    expect(reduceCellStates([])).toBe('pending');
  });

  it('failed wins over everything else', () => {
    expect(reduceCellStates(['passed', 'pending', 'failed', 'scored'])).toBe(
      'failed'
    );
  });

  it('error wins over inFlight/pending/scored/na/passed', () => {
    expect(reduceCellStates(['passed', 'error', 'na'])).toBe('error');
  });

  it('inFlight wins over pending', () => {
    expect(reduceCellStates(['pending', 'inFlight'])).toBe('inFlight');
  });

  it('returns passed when all states are passed', () => {
    expect(reduceCellStates(['passed', 'passed'])).toBe('passed');
  });
});

const EMPTY_SET = new Set<string>();

function makeRow(
  metricKey: string,
  verdicts: string,
  overrides: Partial<VerdictRow> = {}
): VerdictRow {
  return {
    requirement_id: 'r1',
    metric_key: metricKey,
    metric_name: metricKey,
    metric_id: null,
    ambiguous: false,
    verdicts,
    overrides: '0'.repeat(verdicts.length),
    passed: 0,
    failed: 0,
    pending: 0,
    ...overrides,
  };
}

describe('computeGroupRollup', () => {
  it('reduces per-test across all metric rows in the group', () => {
    const rows = [makeRow('m1', 'PF.'), makeRow('m2', 'PPF')];
    const testIds = ['t1', 't2', 't3'];
    const rollup = computeGroupRollup(rows, testIds, EMPTY_SET, EMPTY_SET);
    // t1: P,P -> passed. t2: F,P -> failed. t3: .,F -> failed (F wins over .)
    expect(rollup).toEqual(['passed', 'failed', 'failed']);
  });

  it('marks a test in-flight when generating and no metric has failed yet', () => {
    const rows = [makeRow('m1', '.')];
    const testIds = ['t1'];
    const rollup = computeGroupRollup(
      rows,
      testIds,
      new Set(['t1']),
      EMPTY_SET
    );
    expect(rollup).toEqual(['inFlight']);
  });

  it('returns pending for every test when the group has no rows', () => {
    const rollup = computeGroupRollup([], ['t1', 't2'], EMPTY_SET, EMPTY_SET);
    expect(rollup).toEqual(['pending', 'pending']);
  });
});

describe('aggregateGroupByTest', () => {
  it('derives total/passed/failed from the same rollup array', () => {
    const rows = [makeRow('m1', 'PF.'), makeRow('m2', 'PPF')];
    const testIds = ['t1', 't2', 't3'];
    const agg = aggregateGroupByTest(rows, testIds, EMPTY_SET, EMPTY_SET);
    expect(agg.rollup).toEqual(['passed', 'failed', 'failed']);
    expect(agg.total).toBe(3);
    expect(agg.passed).toBe(1);
    expect(agg.failed).toBe(2);
  });

  it('counts error rollup states toward failed, not passed', () => {
    const rows = [makeRow('m1', 'E')];
    const testIds = ['t1'];
    const agg = aggregateGroupByTest(rows, testIds, EMPTY_SET, EMPTY_SET);
    expect(agg.failed).toBe(1);
    expect(agg.passed).toBe(0);
  });

  it('excludes pending tests from both passed and failed', () => {
    const rows = [makeRow('m1', '.')];
    const testIds = ['t1'];
    const agg = aggregateGroupByTest(rows, testIds, EMPTY_SET, EMPTY_SET);
    expect(agg.total).toBe(1);
    expect(agg.passed).toBe(0);
    expect(agg.failed).toBe(0);
  });
});

describe('aggregateMetric', () => {
  it('computes pass rate from row counts', () => {
    const row: VerdictRow = {
      requirement_id: 'r1',
      metric_key: 'm1',
      metric_name: 'M1',
      metric_id: null,
      ambiguous: false,
      verdicts: '',
      overrides: '',
      passed: 3,
      failed: 1,
      pending: 0,
    };
    expect(aggregateMetric(row)).toEqual({ passRate: 0.75 });
  });

  it('returns null when both passed and failed are 0', () => {
    const row: VerdictRow = {
      requirement_id: 'r1',
      metric_key: 'm1',
      metric_name: 'M1',
      metric_id: null,
      ambiguous: false,
      verdicts: '',
      overrides: '',
      passed: 0,
      failed: 0,
      pending: 5,
    };
    expect(aggregateMetric(row)).toEqual({ passRate: null });
  });
});
