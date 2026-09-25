import {
  CHAR_TO_STATE,
  aggregateMetric,
  metriclessRow,
} from '../verdict-model';
import type { VerdictRow } from '@/utils/api-client/interfaces/test-run';
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
