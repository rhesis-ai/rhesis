import {
  CHAR_TO_STATE,
  aggregateMetric,
  computeVerdictBlocks,
  formatVerdictBlocks,
} from '../verdict-model';
import type {
  VerdictRequirement,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';

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
  it('computes pass rate from row counts', () => {
    expect(aggregateMetric(makeRow({ passed: 3, failed: 1 }))).toEqual({
      passRate: 0.75,
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
    ).toEqual({ passRate: 0.5 });
  });
});

describe('computeVerdictBlocks', () => {
  function makeRequirement(
    overrides: Partial<VerdictRequirement> = {}
  ): VerdictRequirement {
    return { id: 'r1', name: 'R1', metric_keys: ['m1'], ...overrides };
  }

  it('derives tests x metrics per requirement', () => {
    const blocks = computeVerdictBlocks(
      [makeRequirement({ metric_keys: ['m1', 'm2'] })],
      [makeRow({ metric_key: 'm1', passed: 20, failed: 5, pending: 2 })]
    );
    expect(blocks).toEqual([{ tests: 27, metrics: 2 }]);
  });

  it('keeps requirements with different test scopes apart', () => {
    const blocks = computeVerdictBlocks(
      [
        makeRequirement({ id: 'r1', metric_keys: ['m1'] }),
        makeRequirement({ id: 'r2', metric_keys: ['m2'] }),
      ],
      [
        makeRow({ metric_key: 'm1', passed: 27 }),
        makeRow({ metric_key: 'm2', passed: 11 }),
      ]
    );
    expect(blocks).toEqual([
      { tests: 27, metrics: 1 },
      { tests: 11, metrics: 1 },
    ]);
  });

  it('reports zero tests for a requirement with no rows', () => {
    expect(computeVerdictBlocks([makeRequirement()], [])).toEqual([
      { tests: 0, metrics: 1 },
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
