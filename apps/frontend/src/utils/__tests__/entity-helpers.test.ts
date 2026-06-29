import {
  buildLinkedEntityUrl,
  getEntityDisplayName,
  getEntityPath,
  getEntityUrlMap,
  getEntityIconName,
  isValidEntityType,
} from '../entity-helpers';
import { EntityType } from '@/types/entity-type';

describe('getEntityDisplayName', () => {
  it('returns display names for all entity types', () => {
    expect(getEntityDisplayName(EntityType.TEST)).toBe('Test');
    expect(getEntityDisplayName(EntityType.TEST_SET)).toBe('Test Set');
    expect(getEntityDisplayName(EntityType.TEST_RUN)).toBe('Test Run');
    expect(getEntityDisplayName(EntityType.TEST_RESULT)).toBe('Test Result');
    expect(getEntityDisplayName(EntityType.TASK)).toBe('Task');
    expect(getEntityDisplayName(EntityType.SOURCE)).toBe('Source');
    expect(getEntityDisplayName(EntityType.TRACE)).toBe('Trace');
  });

  it('falls back to raw entity type for unknown types', () => {
    // @ts-expect-error testing unknown type
    expect(getEntityDisplayName('Unknown')).toBe('Unknown');
  });
});

describe('getEntityPath', () => {
  it('returns URL paths for all entity types', () => {
    expect(getEntityPath(EntityType.TEST)).toBe('tests');
    expect(getEntityPath(EntityType.TEST_SET)).toBe('test-sets');
    expect(getEntityPath(EntityType.TEST_RUN)).toBe('test-runs');
    expect(getEntityPath(EntityType.TEST_RESULT)).toBe('test-results');
    expect(getEntityPath(EntityType.TASK)).toBe('tasks');
    expect(getEntityPath(EntityType.SOURCE)).toBe('knowledge');
    expect(getEntityPath(EntityType.TRACE)).toBe('traces');
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
    expect(map[EntityType.TEST]).toBe('tests');
    expect(map[EntityType.TEST_SET]).toBe('test-sets');
    expect(map[EntityType.SOURCE]).toBe('knowledge');
  });
});

describe('getEntityIconName', () => {
  it('returns icon names for all entity types', () => {
    expect(getEntityIconName(EntityType.TEST)).toBe('Science');
    expect(getEntityIconName(EntityType.TEST_SET)).toBe('Category');
    expect(getEntityIconName(EntityType.TEST_RUN)).toBe('PlayArrow');
    expect(getEntityIconName(EntityType.TEST_RESULT)).toBe('Assignment');
    expect(getEntityIconName(EntityType.TASK)).toBe('Assignment');
    expect(getEntityIconName(EntityType.SOURCE)).toBe('Description');
    expect(getEntityIconName(EntityType.TRACE)).toBe('Timeline');
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
      buildLinkedEntityUrl({
        entity_type: EntityType.TEST,
        entity_id: undefined,
      })
    ).toBeNull();
  });

  it('builds a standard entity URL', () => {
    expect(
      buildLinkedEntityUrl({
        entity_type: EntityType.TEST,
        entity_id: 'test-id',
      })
    ).toBe('/tests/test-id');
  });

  it('builds a test run URL for test results', () => {
    expect(
      buildLinkedEntityUrl({
        entity_type: EntityType.TEST_RESULT,
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
    expect(isValidEntityType(EntityType.TEST)).toBe(true);
    expect(isValidEntityType(EntityType.TEST_SET)).toBe(true);
    expect(isValidEntityType(EntityType.TEST_RUN)).toBe(true);
    expect(isValidEntityType(EntityType.TEST_RESULT)).toBe(true);
    expect(isValidEntityType(EntityType.TASK)).toBe(true);
    expect(isValidEntityType(EntityType.SOURCE)).toBe(true);
    expect(isValidEntityType(EntityType.TRACE)).toBe(true);
  });

  it('returns false for invalid entity types', () => {
    expect(isValidEntityType('Invalid')).toBe(false);
    expect(isValidEntityType('')).toBe(false);
    expect(isValidEntityType('test')).toBe(false); // case-sensitive
  });
});
