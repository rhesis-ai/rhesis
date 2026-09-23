import {
  CHAR_TO_STATE,
  aggregateMetric,
  computeVerdictBlocks,
  formatVerdictBlocks,
  metriclessRow,
} from '../verdict-model';
import type {
  VerdictRequirement,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';
import { passRate } from '@/constants/outcomes';

// Time-dependent state derivation lives in verdict-timeline.ts and is covered
// by verdict-timeline.test.ts; this file covers what stays time-independent.

function makeRow(overrides: Partial<VerdictRow> = {}): VerdictRow {
  return {
    requirement_id: 'r1',
    metric_key: 'm1',
    metric_name: 'M1',
    metric_id: null,
    ambiguous: false,
    verdicts: '',
    overrides: '',
    passed: 0,
    failed: 0,
    pending: 0,
    ...overrides,
  };
}

describe('CHAR_TO_STATE', () => {
  it.each([
    ['.', 'pending'],
    ['P', 'passed'],
    ['F', 'failed'],
    ['S', 'scored'],
    ['E', 'error'],
    ['X', 'na'],
  ] as const)('maps %s to %s', (char, expected) => {
    expect(CHAR_TO_STATE[char]).toBe(expected);
  });

  it('has no mapping for an unknown char', () => {
    expect(CHAR_TO_STATE['?']).toBeUndefined();
  });
});

describe('aggregateMetric', () => {
  it('computes pass rate from row counts, as a percentage', () => {
    expect(aggregateMetric(makeRow({ passed: 3, failed: 1 }))).toEqual({
      passRate: 75,
    });
  });

  it('returns null when nothing has resolved yet', () => {
    expect(aggregateMetric(makeRow({ pending: 5 }))).toEqual({
      passRate: null,
    });
  });

  it('excludes pending from the denominator', () => {
    expect(
      aggregateMetric(makeRow({ passed: 1, failed: 1, pending: 8 }))
    ).toEqual({ passRate: 50 });
  });

  it('agrees with the shared pass-rate formula', () => {
    // Same scale, same helper -- so a row's number and its review-status
    // chip can never band off different arithmetic.
    expect(aggregateMetric(makeRow({ passed: 7, failed: 3 })).passRate).toBe(
      passRate(7, 3)
    );
  });
});

describe('computeVerdictBlocks', () => {
  function makeRequirement(
    overrides: Partial<VerdictRequirement> = {}
  ): VerdictRequirement {
    return {
      id: 'r1',
      name: 'R1',
      metric_keys: ['m1'],
      test_status: '',
      ...overrides,
    };
  }

  it('derives tests x metrics per requirement', () => {
    const blocks = computeVerdictBlocks(
      [makeRequirement({ metric_keys: ['m1', 'm2'] })],
      [
        makeRow({ metric_key: 'm1', verdicts: 'PF.' }),
        makeRow({ metric_key: 'm2', verdicts: 'PP.' }),
      ]
    );
    expect(blocks).toEqual([{ tests: 3, metrics: 2 }]);
  });

  it('keeps requirements with different test scopes apart', () => {
    const blocks = computeVerdictBlocks(
      [
        makeRequirement({ id: 'r1', metric_keys: ['m1'] }),
        makeRequirement({ id: 'r2', metric_keys: ['m2'] }),
      ],
      [
        makeRow({ metric_key: 'm1', verdicts: 'PPX' }),
        makeRow({ requirement_id: 'r2', metric_key: 'm2', verdicts: 'XXP' }),
      ]
    );
    expect(blocks).toEqual([
      { tests: 2, metrics: 1 },
      { tests: 1, metrics: 1 },
    ]);
  });

  it('reads each requirement from its own row when two share a metric key', () => {
    const blocks = computeVerdictBlocks(
      [
        makeRequirement({ id: 'r1', metric_keys: ['m1'] }),
        makeRequirement({ id: 'r2', metric_keys: ['m1'] }),
      ],
      [
        makeRow({ requirement_id: 'r1', metric_key: 'm1', verdicts: 'PXX' }),
        makeRow({ requirement_id: 'r2', metric_key: 'm1', verdicts: 'XPP' }),
      ]
    );
    expect(blocks).toEqual([
      { tests: 1, metrics: 1 },
      { tests: 2, metrics: 1 },
    ]);
  });

  it('ignores a metric scoped out of every test, even as the first row', () => {
    // Nicolai's run: a multi-turn metric on single-turn tests came first and
    // made the whole requirement read as zero tests.
    const blocks = computeVerdictBlocks(
      [makeRequirement({ metric_keys: ['goal', 'm1', 'm2'] })],
      [
        makeRow({ metric_key: 'goal', verdicts: 'XXXXX' }),
        makeRow({ metric_key: 'm1', verdicts: 'XXPPX' }),
        makeRow({ metric_key: 'm2', verdicts: 'XXPPX' }),
      ]
    );
    expect(blocks).toEqual([{ tests: 2, metrics: 2 }]);
  });

  it('reports an empty block for a requirement with no rows', () => {
    expect(computeVerdictBlocks([makeRequirement()], [])).toEqual([
      { tests: 0, metrics: 0 },
    ]);
  });
});

describe('formatVerdictBlocks', () => {
  it('renders a single block', () => {
    expect(formatVerdictBlocks([{ tests: 38, metrics: 7 }])).toBe(
      'blocks: 38×7'
    );
  });

  it('joins two blocks with "and"', () => {
    expect(
      formatVerdictBlocks([
        { tests: 27, metrics: 7 },
        { tests: 11, metrics: 3 },
      ])
    ).toBe('blocks: 27×7 and 11×3');
  });

  it('comma-separates three or more', () => {
    expect(
      formatVerdictBlocks([
        { tests: 1, metrics: 1 },
        { tests: 2, metrics: 2 },
        { tests: 3, metrics: 3 },
      ])
    ).toBe('blocks: 1×1, 2×2 and 3×3');
  });

  it('skips empty blocks', () => {
    expect(
      formatVerdictBlocks([
        { tests: 0, metrics: 4 },
        { tests: 5, metrics: 2 },
      ])
    ).toBe('blocks: 5×2');
  });

  it('returns an empty string when nothing is renderable', () => {
    expect(formatVerdictBlocks([{ tests: 0, metrics: 0 }])).toBe('');
  });
});

describe('metriclessRow', () => {
  const requirement = (metric_keys: string[], test_status: string) => ({
    id: 'r1',
    name: 'R1',
    metric_keys,
    test_status,
  });

  it('carries the tests of a requirement with no metrics', () => {
    expect(metriclessRow(requirement([], 'XES.P'))).toMatchObject({
      requirement_id: 'r1',
      verdicts: 'XES.P',
      passed: 1,
      failed: 1,
      pending: 1,
    });
  });

  it('is null when the requirement has metrics of its own', () => {
    expect(metriclessRow(requirement(['m1'], 'XEX'))).toBeNull();
  });

  it('is null when the requirement owns no column', () => {
    expect(metriclessRow(requirement([], 'XXX'))).toBeNull();
    expect(metriclessRow(requirement([], ''))).toBeNull();
  });
});
