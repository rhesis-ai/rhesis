import { EntityType } from '@/types/entity-type';
import type { TaskMetadata } from '@/utils/api-client/interfaces/task';

/**
 * Get the display name for an entity type
 * @param entityType The entity type
 * @returns The display name for the entity
 */
export const getEntityDisplayName = (entityType: EntityType): string => {
  const entityMap: Partial<Record<EntityType, string>> = {
    [EntityType.TEST]: 'Test',
    [EntityType.TEST_SET]: 'Test Set',
    [EntityType.TEST_RUN]: 'Test Run',
    [EntityType.TEST_RESULT]: 'Test Result',
    [EntityType.TASK]: 'Task',
    [EntityType.SOURCE]: 'Source',
    [EntityType.TRACE]: 'Trace',
  };
  return entityMap[entityType] || entityType;
};

/**
 * Get the URL path for an entity type (plural form)
 * @param entityType The entity type
 * @returns The URL path for the entity
 */
export const getEntityPath = (entityType: EntityType): string => {
  const pathMap: Partial<Record<EntityType, string>> = {
    [EntityType.TEST]: 'tests',
    [EntityType.TEST_SET]: 'test-sets',
    [EntityType.TEST_RUN]: 'test-runs',
    [EntityType.TEST_RESULT]: 'test-results',
    [EntityType.TASK]: 'tasks',
    [EntityType.SOURCE]: 'knowledge',
    [EntityType.TRACE]: 'traces',
  };
  return pathMap[entityType] || entityType.toLowerCase();
};

/**
 * Get the entity URL map for navigation
 * @returns A record mapping entity types to their URL paths
 */
export const getEntityUrlMap = (): Record<string, string> => {
  return {
    [EntityType.TEST]: 'tests',
    [EntityType.TEST_SET]: 'test-sets',
    [EntityType.TEST_RUN]: 'test-runs',
    [EntityType.TEST_RESULT]: 'test-results',
    [EntityType.TASK]: 'tasks',
    [EntityType.SOURCE]: 'knowledge',
    [EntityType.TRACE]: 'traces',
  };
};

/**
 * Get the icon name for an entity type
 * @param entityType The entity type
 * @returns The icon name for the entity
 */
export const getEntityIconName = (entityType: EntityType): string => {
  const iconMap: Partial<Record<EntityType, string>> = {
    [EntityType.TEST]: 'Science',
    [EntityType.TEST_SET]: 'Category',
    [EntityType.TEST_RUN]: 'PlayArrow',
    [EntityType.TEST_RESULT]: 'Assignment',
    [EntityType.TASK]: 'Assignment',
    [EntityType.SOURCE]: 'Description',
    [EntityType.TRACE]: 'Timeline',
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
    EntityType.TEST,
    EntityType.TEST_SET,
    EntityType.TEST_RUN,
    EntityType.TEST_RESULT,
    EntityType.TASK,
    EntityType.SOURCE,
    EntityType.TRACE,
  ];
  return validTypes.includes(entityType as EntityType);
};

/**
 * Build a navigation URL for a task's linked entity (comment, test result, etc.).
 */
export const buildLinkedEntityUrl = (task: {
  entity_type?: string;
  entity_id?: string;
  task_metadata?: TaskMetadata;
}): string | null => {
  if (!task.entity_type || !task.entity_id) {
    return null;
  }

  if (
    task.entity_type === EntityType.TEST_RESULT &&
    task.task_metadata?.test_run_id
  ) {
    const queryParams = new URLSearchParams();
    queryParams.append('selectedresult', task.entity_id);
    const queryString = queryParams.toString();
    const commentHash = task.task_metadata?.comment_id
      ? `#comment-${task.task_metadata.comment_id}`
      : '';
    return `/test-runs/${task.task_metadata.test_run_id}?${queryString}${commentHash}`;
  }

  const entityUrlMap = getEntityUrlMap();
  const entityPath =
    entityUrlMap[task.entity_type] || task.entity_type.toLowerCase();
  const baseUrl = `/${entityPath}/${task.entity_id}`;

  const queryParams = new URLSearchParams();
  if (task.task_metadata?.test_result_id) {
    queryParams.append(
      'selectedresult',
      String(task.task_metadata.test_result_id)
    );
  }
  const queryString = queryParams.toString()
    ? `?${queryParams.toString()}`
    : '';
  const commentHash = task.task_metadata?.comment_id
    ? `#comment-${task.task_metadata.comment_id}`
    : '';

  return `${baseUrl}${queryString}${commentHash}`;
};

/**
 * Generate a duplicate name with an incrementing "(Copy N)" suffix.
 * - "Foo"          → "Foo (Copy)"
 * - "Foo (Copy)"   → "Foo (Copy 2)"
 * - "Foo (Copy 2)" → "Foo (Copy 3)"
 */
export const generateCopyName = (name: string): string => {
  const copyPattern = /^(.*) \(Copy(?: (\d+))?\)$/;
  const match = name.match(copyPattern);

  if (match) {
    const baseName = match[1];
    const currentNumber = match[2] ? parseInt(match[2], 10) : 1;
    return `${baseName} (Copy ${currentNumber + 1})`;
  }

  return `${name} (Copy)`;
};
