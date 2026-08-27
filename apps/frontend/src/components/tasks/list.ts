import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Task } from '@/types/tasks';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';

export const ENTITY_TASKS_FILTERS = {} as const;

/**
 * The tasks attached to one entity (a detail page's Tasks tab), newest first.
 * The entity scope is part of the descriptor rather than a filter so the
 * server prefetch and the client grid can't disagree on it.
 */
export function entityTasksList(entityType: string, entityId: string) {
  return defineList<Task, typeof ENTITY_TASKS_FILTERS>({
    title: 'Tasks',
    resource: 'tasks',
    capability: Capability.Task.READ,
    defaultPageSize: 10,
    filters: ENTITY_TASKS_FILTERS,
    list: (factory: ApiClientFactory, params) =>
      factory.getTasksClient().getTasks({
        ...params,
        $filter: `entity_type eq '${escapeODataValue(entityType)}' and entity_id eq '${escapeODataValue(entityId)}'`,
      }),
  });
}
