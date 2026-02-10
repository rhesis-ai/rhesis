import {
  getEntityDisplayName,
  getEntityPath,
  getEntityUrlMap,
  getEntityIconName,
  isValidEntityType,
} from '../entity-helpers';

describe('getEntityDisplayName', () => {
  it('returns display names for all entity types', () => {
    expect(getEntityDisplayName('Test')).toBe('Test');
    expect(getEntityDisplayName('TestSet')).toBe('Test Set');
    expect(getEntityDisplayName('TestRun')).toBe('Test Run');
    expect(getEntityDisplayName('TestResult')).toBe('Test Result');
    expect(getEntityDisplayName('Task')).toBe('Task');
    expect(getEntityDisplayName('Source')).toBe('Source');
  });

  it('falls back to raw entity type for unknown types', () => {
    // @ts-expect-error testing unknown type
    expect(getEntityDisplayName('Unknown')).toBe('Unknown');
  });
});

describe('getEntityPath', () => {
  it('returns URL paths for all entity types', () => {
    expect(getEntityPath('Test')).toBe('tests');
    expect(getEntityPath('TestSet')).toBe('test-sets');
    expect(getEntityPath('TestRun')).toBe('test-runs');
    expect(getEntityPath('TestResult')).toBe('test-results');
    expect(getEntityPath('Task')).toBe('tasks');
    expect(getEntityPath('Source')).toBe('knowledge');
  });

  it('falls back to lowercase for unknown types', () => {
    // @ts-expect-error testing unknown type
    expect(getEntityPath('Unknown')).toBe('unknown');
  });
});

describe('getEntityUrlMap', () => {
  it('returns a complete mapping', () => {
    const map = getEntityUrlMap();
    expect(Object.keys(map)).toHaveLength(6);
    expect(map.Test).toBe('tests');
    expect(map.TestSet).toBe('test-sets');
    expect(map.Source).toBe('knowledge');
  });
});

describe('getEntityIconName', () => {
  it('returns icon names for all entity types', () => {
    expect(getEntityIconName('Test')).toBe('Science');
    expect(getEntityIconName('TestSet')).toBe('Category');
    expect(getEntityIconName('TestRun')).toBe('PlayArrow');
    expect(getEntityIconName('TestResult')).toBe('Assignment');
    expect(getEntityIconName('Task')).toBe('Assignment');
    expect(getEntityIconName('Source')).toBe('Description');
  });

  it('falls back to Assignment for unknown types', () => {
    // @ts-expect-error testing unknown type
    expect(getEntityIconName('Unknown')).toBe('Assignment');
  });
});

describe('isValidEntityType', () => {
  it('returns true for valid entity types', () => {
    expect(isValidEntityType('Test')).toBe(true);
    expect(isValidEntityType('TestSet')).toBe(true);
    expect(isValidEntityType('TestRun')).toBe(true);
    expect(isValidEntityType('TestResult')).toBe(true);
    expect(isValidEntityType('Task')).toBe(true);
    expect(isValidEntityType('Source')).toBe(true);
  });

  it('returns false for invalid entity types', () => {
    expect(isValidEntityType('Invalid')).toBe(false);
    expect(isValidEntityType('')).toBe(false);
    expect(isValidEntityType('test')).toBe(false); // case-sensitive
  });
});
