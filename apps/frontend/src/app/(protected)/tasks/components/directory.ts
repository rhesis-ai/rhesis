import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineDirectory } from '@/utils/directory';

const TASKS_FILTERS = {
  search: { kind: 'search', columns: ['title', 'description'] },
  status: { kind: 'enum', column: 'status/name' },
  priority: { kind: 'enum', column: 'priority/type_value' },
  assignee: { kind: 'enum', column: 'assignee/name' },
} as const;

/**
 * Not SSR-prefetched, unlike most other directories: tasks must always
 * refetch on arrival (a task assigned to you while elsewhere must show up),
 * which server-rendered `initialData` would short-circuit on the client.
 */
export const tasksDirectory = defineDirectory({
  title: 'Tasks',
  resource: 'tasks',
  capability: Capability.Task.READ,
  defaultPageSize: 25,
  filters: TASKS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getTasksClient().getTasks(params),
});
