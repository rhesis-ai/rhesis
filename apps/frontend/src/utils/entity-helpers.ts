import { EntityType } from '@/types/tasks';

/**
 * Get the display name for an entity type
 * @param entityType The entity type
 * @returns The display name for the entity
 */
export const getEntityDisplayName = (entityType: EntityType): string => {
  const entityMap: Record<EntityType, string> = {
    Test: 'Test',
    TestSet: 'Test Set',
    TestRun: 'Test Run',
    TestResult: 'Test Result',
    Task: 'Task',
    Source: 'Source',
  };
  return entityMap[entityType] || entityType;
};

/**
 * Get the URL path for an entity type (plural form)
 * @param entityType The entity type
 * @returns The URL path for the entity
 */
export const getEntityPath = (entityType: EntityType): string => {
  const pathMap: Record<EntityType, string> = {
    Test: 'tests',
    TestSet: 'test-sets',
    TestRun: 'test-runs',
    TestResult: 'test-results',
    Task: 'tasks',
    Source: 'knowledge',
  };
  return pathMap[entityType] || entityType.toLowerCase();
};

/**
 * Get the entity URL map for navigation
 * @returns A record mapping entity types to their URL paths
 */
export const getEntityUrlMap = (): Record<string, string> => {
  return {
    Test: 'tests',
    TestSet: 'test-sets',
    TestRun: 'test-runs',
    TestResult: 'test-results',
    Task: 'tasks',
    Source: 'knowledge',
  };
};

/**
 * Get the icon name for an entity type
 * @param entityType The entity type
 * @returns The icon name for the entity
 */
export const getEntityIconName = (entityType: EntityType): string => {
  const iconMap: Record<EntityType, string> = {
    Test: 'Science',
    TestSet: 'Category',
    TestRun: 'PlayArrow',
    TestResult: 'Assignment',
    Task: 'Assignment',
    Source: 'Description',
  };
  return iconMap[entityType] || 'Assignment';
};

/**
 * Check if an entity type is valid
 * @param entityType The entity type to validate
 * @returns True if the entity type is valid
 */
export const isValidEntityType = (
  entityType: string
): entityType is EntityType => {
  const validTypes: EntityType[] = [
    'Test',
    'TestSet',
    'TestRun',
    'TestResult',
    'Task',
    'Source',
  ];
  return validTypes.includes(entityType as EntityType);
};
