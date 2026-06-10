import {
  buildLinkedEntityUrl,
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
    expect(getEntityDisplayName('Trace')).toBe('Trace');
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
    expect(getEntityPath('Trace')).toBe('traces');
  });

  it('falls back to lowercase for unknown types', () => {
    // @ts-expect-error testing unknown type
    expect(getEntityPath('Unknown')).toBe('unknown');
  });
});

describe('getEntityUrlMap', () => {
  it('returns a complete mapping', () => {
    const map = getEntityUrlMap();
    expect(Object.keys(map)).toHaveLength(7);
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
    expect(getEntityIconName('Trace')).toBe('Timeline');
  });

  it('falls back to Assignment for unknown types', () => {
    // @ts-expect-error testing unknown type
    expect(getEntityIconName('Unknown')).toBe('Assignment');
  });
});

describe('buildLinkedEntityUrl', () => {
  it('returns null when entity is missing', () => {
    expect(buildLinkedEntityUrl({})).toBeNull();
    expect(
      buildLinkedEntityUrl({ entity_type: 'Test', entity_id: undefined })
    ).toBeNull();
  });

  it('builds a standard entity URL', () => {
    expect(
      buildLinkedEntityUrl({
        entity_type: 'Test',
        entity_id: 'test-id',
      })
    ).toBe('/tests/test-id');
  });

  it('builds a test run URL for test results', () => {
    expect(
      buildLinkedEntityUrl({
        entity_type: 'TestResult',
        entity_id: 'result-id',
        task_metadata: {
          test_run_id: 'run-id',
          comment_id: 'comment-id',
        },
      })
    ).toBe('/test-runs/run-id?selectedresult=result-id#comment-comment-id');
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
    expect(isValidEntityType('Trace')).toBe(true);
  });

  it('returns false for invalid entity types', () => {
    expect(isValidEntityType('Invalid')).toBe(false);
    expect(isValidEntityType('')).toBe(false);
    expect(isValidEntityType('test')).toBe(false); // case-sensitive
  });
});
