import {
  TEST_TYPES,
  getTestType,
  isMultiTurnTest,
  isSingleTurnTest,
} from '../test-types';

describe('getTestType', () => {
  it('returns matching test type for exact match', () => {
    expect(getTestType('Single-Turn')).toBe(TEST_TYPES.SINGLE_TURN);
    expect(getTestType('Multi-Turn')).toBe(TEST_TYPES.MULTI_TURN);
  });

  it('matches case-insensitively', () => {
    expect(getTestType('single-turn')).toBe(TEST_TYPES.SINGLE_TURN);
    expect(getTestType('MULTI-TURN')).toBe(TEST_TYPES.MULTI_TURN);
    expect(getTestType('Single-turn')).toBe(TEST_TYPES.SINGLE_TURN);
  });

  it('returns null for unknown types', () => {
    expect(getTestType('unknown')).toBeNull();
    expect(getTestType('batch')).toBeNull();
  });

  it('returns null for null/undefined/empty', () => {
    expect(getTestType(null)).toBeNull();
    expect(getTestType(undefined)).toBeNull();
    expect(getTestType('')).toBeNull();
  });
});

describe('isMultiTurnTest', () => {
  it('returns true for multi-turn values', () => {
    expect(isMultiTurnTest('Multi-Turn')).toBe(true);
    expect(isMultiTurnTest('multi-turn')).toBe(true);
    expect(isMultiTurnTest('MULTI-TURN')).toBe(true);
  });

  it('returns false for single-turn values', () => {
    expect(isMultiTurnTest('Single-Turn')).toBe(false);
  });

  it('returns false for null/undefined', () => {
    expect(isMultiTurnTest(null)).toBe(false);
    expect(isMultiTurnTest(undefined)).toBe(false);
  });
});

describe('isSingleTurnTest', () => {
  it('returns true for single-turn values', () => {
    expect(isSingleTurnTest('Single-Turn')).toBe(true);
    expect(isSingleTurnTest('single-turn')).toBe(true);
    expect(isSingleTurnTest('SINGLE-TURN')).toBe(true);
  });

  it('returns false for multi-turn values', () => {
    expect(isSingleTurnTest('Multi-Turn')).toBe(false);
  });

  it('returns false for null/undefined', () => {
    expect(isSingleTurnTest(null)).toBe(false);
    expect(isSingleTurnTest(undefined)).toBe(false);
  });
});

describe('TEST_TYPES constants', () => {
  it('has expected values', () => {
    expect(TEST_TYPES.SINGLE_TURN).toBe('Single-Turn');
    expect(TEST_TYPES.MULTI_TURN).toBe('Multi-Turn');
  });
});
